"""
File extraction module for images, PDFs, and other document types.
Provides OCR, vision LLM descriptions, and text extraction.
"""

import logging
import os
import hashlib
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from io import BytesIO

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supported file types by category
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif'}
PDF_EXTENSIONS = {'.pdf'}
DOCUMENT_EXTENSIONS = {'.docx', '.doc', '.odt', '.rtf'}
TEXT_EXTENSIONS = {'.txt', '.md', '.html', '.json', '.yaml', '.yml', '.py', '.js', '.ts', '.sql', '.xml', '.csv'}

# Thumbnail settings
THUMBNAIL_SIZE = (300, 300)
THUMBNAIL_DIR = os.environ.get("THUMBNAIL_DIR")
if not THUMBNAIL_DIR:
    if os.path.exists("/app/shared/thumbnails"):
        THUMBNAIL_DIR = "/app/shared/thumbnails"
    else:
        THUMBNAIL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "shared", "thumbnails")


def get_file_type(extension: str) -> str:
    """Determine the file type category from extension."""
    ext = extension.lower()
    if ext in IMAGE_EXTENSIONS:
        return 'image'
    elif ext in PDF_EXTENSIONS:
        return 'pdf'
    elif ext in DOCUMENT_EXTENSIONS:
        return 'document'
    elif ext in TEXT_EXTENSIONS:
        return 'text'
    else:
        return 'unknown'


def generate_thumbnail(file_path: Path, sha256: str) -> Optional[str]:
    """
    Generate a thumbnail for an image or PDF.
    Returns the relative path to the thumbnail or None if failed.
    """
    if not PIL_AVAILABLE:
        logger.warning("PIL not available, skipping thumbnail generation")
        return None
    
    try:
        os.makedirs(THUMBNAIL_DIR, exist_ok=True)
        thumbnail_filename = f"{sha256[:16]}.jpg"
        thumbnail_path = os.path.join(THUMBNAIL_DIR, thumbnail_filename)
        
        # If thumbnail already exists, return it
        if os.path.exists(thumbnail_path):
            return thumbnail_filename
        
        ext = file_path.suffix.lower()
        
        if ext in IMAGE_EXTENSIONS:
            # Generate from image
            with Image.open(file_path) as img:
                # Convert to RGB if necessary (handles PNG with transparency, etc.)
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')
                img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                img.save(thumbnail_path, "JPEG", quality=85)
                
        elif ext in PDF_EXTENSIONS and PYMUPDF_AVAILABLE:
            # Generate from first page of PDF
            doc = fitz.open(file_path)
            if doc.page_count > 0:
                page = doc[0]
                # Render at 150 DPI
                mat = fitz.Matrix(150/72, 150/72)
                pix = page.get_pixmap(matrix=mat)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                img.save(thumbnail_path, "JPEG", quality=85)
            doc.close()
        else:
            return None
        
        logger.info(f"Generated thumbnail: {thumbnail_filename}")
        return thumbnail_filename
        
    except Exception as e:
        logger.error(f"Failed to generate thumbnail for {file_path}: {e}")
        return None


def extract_text_from_image(file_path: Path) -> Tuple[str, Dict[str, Any]]:
    """
    Extract text from image using OCR.
    Returns (extracted_text, metadata_dict).
    """
    ocr_text = ""
    metadata = {
        "ocr_confidence": None,
        "image_width": None,
        "image_height": None,
        "image_format": None,
    }
    
    if not PIL_AVAILABLE:
        logger.warning("PIL not available, cannot process image")
        return "", metadata
    
    try:
        with Image.open(file_path) as img:
            metadata["image_width"] = img.width
            metadata["image_height"] = img.height
            metadata["image_format"] = img.format
            
            if TESSERACT_AVAILABLE:
                # Perform OCR
                try:
                    # Get detailed OCR data including confidence
                    ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                    
                    # Extract text and calculate average confidence
                    texts = []
                    confidences = []
                    for i, text in enumerate(ocr_data['text']):
                        if text.strip():
                            texts.append(text)
                            conf = ocr_data['conf'][i]
                            if conf > 0:  # -1 means no confidence
                                confidences.append(conf)
                    
                    ocr_text = ' '.join(texts)
                    if confidences:
                        metadata["ocr_confidence"] = round(sum(confidences) / len(confidences), 2)
                    
                    logger.info(f"OCR extracted {len(ocr_text)} chars from {file_path.name}")
                    
                except Exception as e:
                    logger.warning(f"OCR failed for {file_path}: {e}")
                    # Fall back to simple OCR
                    ocr_text = pytesseract.image_to_string(img)
            else:
                logger.warning("Tesseract not available, skipping OCR")
                
    except Exception as e:
        logger.error(f"Failed to process image {file_path}: {e}")
    
    return ocr_text.strip(), metadata


def extract_text_from_pdf(file_path: Path) -> Tuple[str, Dict[str, Any]]:
    """
    Extract text from PDF using PyMuPDF.
    Returns (extracted_text, metadata_dict).
    """
    text = ""
    metadata = {
        "page_count": None,
        "pdf_title": None,
        "pdf_author": None,
        "pdf_subject": None,
        "has_images": False,
        "is_scanned": False,
    }
    
    if not PYMUPDF_AVAILABLE:
        logger.warning("PyMuPDF not available, cannot process PDF")
        return "", metadata
    
    try:
        doc = fitz.open(file_path)
        metadata["page_count"] = doc.page_count
        
        # Extract PDF metadata
        pdf_meta = doc.metadata
        if pdf_meta:
            metadata["pdf_title"] = pdf_meta.get("title")
            metadata["pdf_author"] = pdf_meta.get("author")
            metadata["pdf_subject"] = pdf_meta.get("subject")
        
        # Extract text from all pages
        all_text = []
        total_images = 0
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            page_text = page.get_text()
            all_text.append(page_text)
            
            # Count images
            images = page.get_images()
            total_images += len(images)
        
        text = "\n\n".join(all_text)
        metadata["has_images"] = total_images > 0
        
        # Detect if PDF is scanned (little text but has images)
        if len(text.strip()) < 100 and total_images > 0:
            metadata["is_scanned"] = True
            logger.info(f"PDF appears to be scanned: {file_path.name}")
            
            # Try OCR on scanned PDF
            if TESSERACT_AVAILABLE and PIL_AVAILABLE:
                ocr_texts = []
                for page_num in range(min(doc.page_count, 10)):  # Limit to first 10 pages
                    page = doc[page_num]
                    # Render page to image
                    mat = fitz.Matrix(200/72, 200/72)  # 200 DPI
                    pix = page.get_pixmap(matrix=mat)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    # OCR the page
                    page_ocr = pytesseract.image_to_string(img)
                    if page_ocr.strip():
                        ocr_texts.append(page_ocr)
                
                if ocr_texts:
                    text = "\n\n".join(ocr_texts)
                    logger.info(f"OCR extracted {len(text)} chars from scanned PDF")
        
        doc.close()
        logger.info(f"Extracted {len(text)} chars from PDF: {file_path.name}")
        
    except Exception as e:
        logger.error(f"Failed to process PDF {file_path}: {e}")
    
    return text.strip(), metadata


def extract_file_content(file_path: Path, extension: str) -> Tuple[str, str, Dict[str, Any]]:
    """
    Extract content from any supported file type.
    
    Returns:
        (raw_text, file_type, metadata_dict)
    """
    file_type = get_file_type(extension)
    metadata = {}
    raw_text = ""
    
    try:
        if file_type == 'text':
            # Direct text read
            raw_text = file_path.read_text(errors='ignore')
            raw_text = raw_text.replace('\x00', '')  # Remove NUL characters
            
        elif file_type == 'image':
            raw_text, metadata = extract_text_from_image(file_path)
            
        elif file_type == 'pdf':
            raw_text, metadata = extract_text_from_pdf(file_path)
            
        elif file_type == 'document':
            # TODO: Add support for DOCX, DOC, ODT, RTF
            logger.warning(f"Document extraction not yet implemented for {extension}")
            raw_text = ""
            
        else:
            logger.warning(f"Unsupported file type: {extension}")
            raw_text = ""
            
    except Exception as e:
        logger.error(f"Failed to extract content from {file_path}: {e}")
    
    return raw_text, file_type, metadata


def get_image_dimensions(file_path: Path) -> Tuple[Optional[int], Optional[int]]:
    """Get image dimensions without loading the full image."""
    if not PIL_AVAILABLE:
        return None, None
    
    try:
        with Image.open(file_path) as img:
            return img.width, img.height
    except Exception:
        return None, None
