import logging
import re
from typing import List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import func

from src.db.session import get_db
from src.db.models import RawFile, Entry

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MIN_ENTRY_LENGTH = 50  # Filter out very short segments

def heuristic_split(text: str) -> List[Dict[str, Any]]:
    """
    Splits text into segments based on double newlines or separators.
    Returns a list of dicts with 'text', 'start', 'end'.
    """
    # Simple split by double newlines for now
    # We want to capture start/end indices.
    
    segments = []
    
    # Regex for splitting: 2+ newlines OR separator lines
    # Separators: ====, ----, ***
    separator_pattern = r'\n\s*(?:={3,}|-{3,}|\*{3,})\s*\n'
    double_newline_pattern = r'\n\s*\n'
    
    # Combine patterns? Or just use double newline as primary, and then check for separators?
    # Let's use a combined regex to find split points
    split_pattern = f'(?:{separator_pattern})|(?:{double_newline_pattern})'
    
    # re.finditer is useful here
    # But we want the text BETWEEN matches.
    
    last_end = 0
    for match in re.finditer(split_pattern, text):
        start = last_end
        end = match.start()
        
        segment_text = text[start:end].strip()
        if len(segment_text) >= MIN_ENTRY_LENGTH:
            segments.append({
                'text': segment_text,
                'start': start,
                'end': end
            })
        
        last_end = match.end()
    
    # Add the last segment
    if last_end < len(text):
        segment_text = text[last_end:].strip()
        if len(segment_text) >= MIN_ENTRY_LENGTH:
            segments.append({
                'text': segment_text,
                'start': last_end,
                'end': len(text)
            })
            
    return segments

def segment_file(db: Session, file: RawFile):
    logger.info(f"Segmenting file {file.id}: {file.path}")
    
    # Check if entries already exist
    if file.entries:
        logger.info(f"File {file.id} already has {len(file.entries)} entries. Skipping.")
        return

    segments = heuristic_split(file.raw_text)
    
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
    for i, seg in enumerate(segments):
        entry = Entry(
            file_id=file.id,
            entry_index=i,
            char_start=seg['start'],
            char_end=seg['end'],
            entry_text=seg['text'],
            status='pending'
        )
        new_entries.append(entry)
    
    db.add_all(new_entries)
    db.commit()
    logger.info(f"Created {len(new_entries)} entries for file {file.id}")

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
