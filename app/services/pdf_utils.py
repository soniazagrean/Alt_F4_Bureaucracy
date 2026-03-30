from typing import List, Optional, Tuple
from pathlib import Path
import logging
from PIL import Image
import fitz

logger = logging.getLogger(__name__)

class PDFConversionError(Exception):
    """Custom exception for PDF conversion errors."""
    pass

def pdf_to_pages(
    path: str,
    dpi: int = 300,
    start_page: int = 0,
    end_page: Optional[int] = None,
    max_pages: int = 500
) -> List[Image.Image]:
    """
    Converts a PDF to a list of PIL Images at specified DPI.
    
    Args:
        path: Path to PDF file
        dpi: Resolution in DPI (default 300)
        start_page: Starting page (0-indexed)
        end_page: Ending page (exclusive, None = all pages)
        max_pages: Safety limit on number of pages to process
        
    Returns:
        List of PIL Image objects (RGB mode)
        
    Raises:
        FileNotFoundError: If PDF file doesn't exist
        PDFConversionError: If PDF is invalid, empty, or processing fails
    """
    try:
        pdf_path = Path(path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {path}")
        
        if not pdf_path.is_file():
            raise PDFConversionError(f"Path is not a file: {path}")
        
        images = []
        
        with fitz.open(path) as pdf:
            total_pages = len(pdf)
            if total_pages == 0:
                raise PDFConversionError("PDF contains no pages")
            
            actual_end = end_page if end_page is not None else total_pages
            actual_end = min(actual_end, total_pages)
            actual_end = min(actual_end, start_page + max_pages)
            
            if start_page >= total_pages:
                raise PDFConversionError(
                    f"Start page {start_page} exceeds total pages {total_pages}"
                )
            
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            
            for page_num in range(start_page, actual_end):
                try:
                    page = pdf[page_num]
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    img = Image.frombytes(
                        "RGB",
                        [pix.width, pix.height],
                        pix.samples
                    )
                    img.info['dpi'] = (dpi, dpi)
                    images.append(img)
                    logger.debug(f"Converted page {page_num + 1}")
                except Exception as e:
                    logger.error(f"Failed to convert page {page_num + 1}: {str(e)}")
                    raise PDFConversionError(f"Error converting page {page_num + 1}: {str(e)}")
        
        if not images:
            raise PDFConversionError("No images were successfully converted")
        
        logger.info(f"Successfully converted {len(images)} pages")
        return images
        
    except (FileNotFoundError, PDFConversionError):
        raise
    except Exception as e:
        raise PDFConversionError(f"PDF conversion failed: {str(e)}")


def pdf_to_pages_safe(path: str, **kwargs) -> Tuple[Optional[List[Image.Image]], Optional[str]]:
    """
    Safe wrapper that returns (images, error) tuple instead of raising.
    Useful for Celery tasks where you want graceful error handling.
    """
    try:
        images = pdf_to_pages(path, **kwargs)
        return images, None
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Safe PDF conversion failed: {error_msg}")
        return None, error_msg