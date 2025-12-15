import logging
import re
import hashlib
from typing import List, Dict, Any, Tuple
from html.parser import HTMLParser
from urllib.parse import urlparse

from sqlalchemy.orm import Session
from sqlalchemy import func

from src.db.session import get_db
from src.db.models import RawFile, Entry, DocumentLink

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Segmentation configuration
MIN_ENTRY_LENGTH = 50      # Filter out very short segments
MAX_ENTRY_LENGTH = 4000    # Target max chars per segment (~1000 tokens)
OVERLAP_LENGTH = 200       # Overlap between segments for context continuity


class HTMLTextExtractor(HTMLParser):
    """Extract plain text from HTML, stripping all tags."""
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip_tags = {'script', 'style', 'head', 'meta', 'link'}
        self.current_skip = 0
    
    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.skip_tags:
            self.current_skip += 1
    
    def handle_endtag(self, tag):
        if tag.lower() in self.skip_tags and self.current_skip > 0:
            self.current_skip -= 1
    
    def handle_data(self, data):
        if self.current_skip == 0:
            self.text_parts.append(data)
    
    def get_text(self):
        return ' '.join(self.text_parts)


def strip_html(text: str) -> str:
    """Remove HTML tags and return plain text."""
    try:
        parser = HTMLTextExtractor()
        parser.feed(text)
        return parser.get_text()
    except Exception:
        # Fallback: simple regex strip
        return re.sub(r'<[^>]+>', ' ', text)


def extract_code_blocks(text: str) -> tuple:
    """
    Extract code blocks from markdown text.
    Returns (text_with_placeholders, list_of_code_blocks)
    """
    code_blocks = []
    placeholder_pattern = "<<<CODE_BLOCK_{}>>"
    
    # Match fenced code blocks (```...```)
    def replace_code(match):
        idx = len(code_blocks)
        code_blocks.append({
            'full': match.group(0),
            'lang': match.group(1) or '',
            'code': match.group(2)
        })
        return placeholder_pattern.format(idx)
    
    # Pattern for fenced code blocks
    pattern = r'```(\w*)\n?([\s\S]*?)```'
    text_with_placeholders = re.sub(pattern, replace_code, text)
    
    return text_with_placeholders, code_blocks


def restore_code_blocks(text: str, code_blocks: list) -> str:
    """Restore code blocks from placeholders."""
    for i, block in enumerate(code_blocks):
        placeholder = f"<<<CODE_BLOCK_{i}>>"
        text = text.replace(placeholder, block['full'])
    return text


def extract_markdown_context(text: str) -> str:
    """
    Extract markdown headers to use as context prefix.
    Returns the most recent headers (h1, h2, h3) as context.
    """
    headers = []
    current_h1 = None
    current_h2 = None
    current_h3 = None
    
    for line in text.split('\n'):
        line = line.strip()
        if line.startswith('# '):
            current_h1 = line[2:].strip()
            current_h2 = None
            current_h3 = None
        elif line.startswith('## '):
            current_h2 = line[3:].strip()
            current_h3 = None
        elif line.startswith('### '):
            current_h3 = line[4:].strip()
    
    context_parts = []
    if current_h1:
        context_parts.append(f"# {current_h1}")
    if current_h2:
        context_parts.append(f"## {current_h2}")
    if current_h3:
        context_parts.append(f"### {current_h3}")
    
    return '\n'.join(context_parts)


def extract_links_from_text(text: str) -> List[Dict[str, str]]:
    """
    Extract all links/URLs from text content.
    Returns list of dicts with 'url', 'link_text', 'link_type', 'domain'.
    """
    links = []
    seen_urls = set()
    
    def add_link(url: str, link_text: str, link_type: str):
        """Helper to add unique links."""
        url = url.strip()
        if url in seen_urls or not url:
            return
        seen_urls.add(url)
        
        # Extract domain
        domain = None
        try:
            if url.startswith(('http://', 'https://')):
                parsed = urlparse(url)
                domain = parsed.netloc.lower()
            elif url.startswith('mailto:'):
                domain = url.split('@')[-1].split('?')[0] if '@' in url else None
        except Exception:
            pass
        
        links.append({
            'url': url,
            'link_text': link_text[:500] if link_text else None,  # Truncate long text
            'link_type': link_type,
            'domain': domain
        })
    
    # 1. HTML href links: <a href="...">text</a>
    html_link_pattern = r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>'
    for match in re.finditer(html_link_pattern, text, re.IGNORECASE):
        add_link(match.group(1), match.group(2), 'html_href')
    
    # 2. Markdown links: [text](url)
    markdown_link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    for match in re.finditer(markdown_link_pattern, text):
        add_link(match.group(2), match.group(1), 'markdown')
    
    # 3. Raw URLs (http/https)
    raw_url_pattern = r'(?<!["\'>])https?://[^\s<>"\')\]]+[^\s<>"\')\].,:;!?]'
    for match in re.finditer(raw_url_pattern, text):
        url = match.group(0)
        # Skip if already captured as HTML or markdown
        if url not in seen_urls:
            add_link(url, None, 'raw_url')
    
    # 4. Email addresses
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    for match in re.finditer(email_pattern, text):
        email = f"mailto:{match.group(0)}"
        add_link(email, match.group(0), 'email')
    
    return links


def save_links_for_file(db: Session, file_id: int, links: List[Dict[str, str]]) -> int:
    """
    Save extracted links to the database for a file.
    Returns count of links saved.
    """
    if not links:
        return 0
    
    # Clear existing links for this file
    db.query(DocumentLink).filter(DocumentLink.file_id == file_id).delete()
    
    # Insert new links
    for link_data in links:
        link = DocumentLink(
            file_id=file_id,
            url=link_data['url'],
            link_text=link_data['link_text'],
            link_type=link_data['link_type'],
            domain=link_data['domain']
        )
        db.add(link)
    
    db.commit()
    return len(links)


def find_last_headers_before(text: str, position: int) -> str:
    """
    Find the most recent markdown headers before a given position.
    """
    text_before = text[:position]
    lines = text_before.split('\n')
    
    current_h1 = None
    current_h2 = None
    current_h3 = None
    
    for line in lines:
        line_stripped = line.strip()
        if line_stripped.startswith('# ') and not line_stripped.startswith('##'):
            current_h1 = line_stripped
            current_h2 = None
            current_h3 = None
        elif line_stripped.startswith('## ') and not line_stripped.startswith('###'):
            current_h2 = line_stripped
            current_h3 = None
        elif line_stripped.startswith('### '):
            current_h3 = line_stripped
    
    context_parts = []
    if current_h1:
        context_parts.append(current_h1)
    if current_h2:
        context_parts.append(current_h2)
    if current_h3:
        context_parts.append(current_h3)
    
    return '\n'.join(context_parts)

def split_large_segment(text: str, max_length: int = MAX_ENTRY_LENGTH) -> List[str]:
    """
    Split a large text segment into smaller chunks, respecting sentence boundaries.
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_pos = 0
    
    while current_pos < len(text):
        # Find the end position for this chunk
        end_pos = min(current_pos + max_length, len(text))
        
        if end_pos < len(text):
            # Try to find a sentence boundary (. ! ? followed by space or newline)
            search_start = max(current_pos + max_length // 2, current_pos)
            best_break = end_pos
            
            for pattern in [r'[.!?]\s', r'\n', r',\s', r';\s']:
                matches = list(re.finditer(pattern, text[search_start:end_pos]))
                if matches:
                    best_break = search_start + matches[-1].end()
                    break
            
            end_pos = best_break
        
        chunk = text[current_pos:end_pos].strip()
        if chunk:
            chunks.append(chunk)
        
        current_pos = end_pos
    
    return chunks


def heuristic_split(text: str, is_html: bool = False, is_markdown: bool = False) -> List[Dict[str, Any]]:
    """
    Splits text into segments based on double newlines or separators.
    Returns a list of dicts with 'text', 'start', 'end'.
    Respects max chunk size and adds overlap between segments.
    Preserves markdown headers as context and handles code blocks specially.
    """
    original_text = text
    code_blocks = []
    
    # Strip HTML if needed
    if is_html:
        text = strip_html(text)
    
    # Handle markdown code blocks - extract and preserve them
    if is_markdown:
        text, code_blocks = extract_code_blocks(text)
    
    segments = []
    
    # Regex for splitting: 2+ newlines OR separator lines
    separator_pattern = r'\n\s*(?:={3,}|-{3,}|\*{3,})\s*\n'
    double_newline_pattern = r'\n\s*\n'
    split_pattern = f'(?:{separator_pattern})|(?:{double_newline_pattern})'
    
    raw_segments = []
    last_end = 0
    
    for match in re.finditer(split_pattern, text):
        start = last_end
        end = match.start()
        segment_text = text[start:end].strip()
        if len(segment_text) >= MIN_ENTRY_LENGTH:
            raw_segments.append({
                'text': segment_text,
                'start': start,
                'end': end
            })
        last_end = match.end()
    
    # Add the last segment
    if last_end < len(text):
        segment_text = text[last_end:].strip()
        if len(segment_text) >= MIN_ENTRY_LENGTH:
            raw_segments.append({
                'text': segment_text,
                'start': last_end,
                'end': len(text)
            })
    
    # Now process each segment: split large ones, add overlap and markdown context
    for i, seg in enumerate(raw_segments):
        seg_text = seg['text']
        
        # Add markdown header context if this is a markdown file
        if is_markdown:
            header_context = find_last_headers_before(text, seg['start'])
            if header_context and not seg_text.startswith('#'):
                seg_text = f"{header_context}\n\n{seg_text}"
        
        # Split large segments
        if len(seg_text) > MAX_ENTRY_LENGTH:
            sub_chunks = split_large_segment(seg_text)
            for j, chunk in enumerate(sub_chunks):
                # Restore code blocks in each chunk
                if is_markdown and code_blocks:
                    chunk = restore_code_blocks(chunk, code_blocks)
                segments.append({
                    'text': chunk,
                    'start': seg['start'],  # Approximate
                    'end': seg['end']
                })
        else:
            # Add overlap from previous segment if exists
            if OVERLAP_LENGTH > 0 and i > 0:
                prev_text = raw_segments[i-1]['text']
                overlap = prev_text[-OVERLAP_LENGTH:] if len(prev_text) > OVERLAP_LENGTH else prev_text
                seg_text = f"[...] {overlap}\n\n{seg_text}"
            
            # Restore code blocks
            if is_markdown and code_blocks:
                seg_text = restore_code_blocks(seg_text, code_blocks)
            
            segments.append({
                'text': seg_text,
                'start': seg['start'],
                'end': seg['end']
            })
    
    return segments

def compute_content_hash(text: str) -> str:
    """Compute SHA256 hash of normalized text for deduplication."""
    # Normalize: lowercase, strip whitespace, collapse multiple spaces
    normalized = ' '.join(text.lower().split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def segment_file(db: Session, file: RawFile):
    logger.info(f"Segmenting file {file.id}: {file.path}")
    
    # Check if entries already exist
    if file.entries:
        logger.info(f"File {file.id} already has {len(file.entries)} entries. Skipping.")
        return

    # Detect content type based on extension
    ext = file.extension.lower()
    is_html = ext in ['.html', '.htm']
    is_markdown = ext in ['.md', '.markdown']
    
    # Extract and save links from the raw text
    links = extract_links_from_text(file.raw_text)
    if links:
        link_count = save_links_for_file(db, file.id, links)
        logger.info(f"Extracted {link_count} links from file {file.id}")
    
    segments = heuristic_split(file.raw_text, is_html=is_html, is_markdown=is_markdown)
    
    if not segments:
        logger.warning(f"No segments found for file {file.id}")
        # Maybe create one big entry if it's not empty?
        if len(file.raw_text.strip()) > 0:
             segments = [{
                 'text': file.raw_text.strip(),
                 'start': 0,
                 'end': len(file.raw_text)
             }]
        else:
            return

    new_entries = []
    skipped_duplicates = 0
    
    for i, seg in enumerate(segments):
        # Compute hash for deduplication
        content_hash = compute_content_hash(seg['text'])
        
        # Check if this exact content already exists
        existing = db.query(Entry).filter(Entry.content_hash == content_hash).first()
        if existing:
            logger.debug(f"Skipping duplicate segment (hash: {content_hash[:16]}...)")
            skipped_duplicates += 1
            continue
        
        entry = Entry(
            file_id=file.id,
            entry_index=i,
            char_start=seg['start'],
            char_end=seg['end'],
            entry_text=seg['text'],
            content_hash=content_hash,
            status='pending'
        )
        new_entries.append(entry)
    
    if new_entries:
        db.add_all(new_entries)
        db.commit()
    
    logger.info(f"Created {len(new_entries)} entries for file {file.id} (skipped {skipped_duplicates} duplicates)")

def main():
    db = next(get_db())
    
    # Process files that are 'ok' and don't have entries?
    # Or just iterate all 'ok' files and let segment_file check for existence.
    # For efficiency, we should join or filter.
    
    # Query files that have status 'ok'
    files = db.query(RawFile).filter(RawFile.status == 'ok').all()
    
    for file in files:
        segment_file(db, file)

if __name__ == "__main__":
    main()
