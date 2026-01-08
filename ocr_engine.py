"""
Extract text and bounding boxes from frames using EasyOCR.
"""

import easyocr
from dataclasses import dataclass
import os
import logging

logger = logging.getLogger(__name__)

# Initialize once (loads model)
_reader = None

def get_reader(gpu: bool = False):
    """Get or initialize EasyOCR reader"""
    global _reader
    if _reader is None:
        try:
            _reader = easyocr.Reader(['en'], gpu=gpu)
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {e}")
            raise
    return _reader

@dataclass
class TextRegion:
    text: str
    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2
    confidence: float

def extract_text_regions(image_path: str, gpu: bool = False) -> list[TextRegion]:
    """
    Extract all text regions from an image.
    
    Returns list of TextRegion with text content and bounding box coordinates.
    """
    if not os.path.exists(image_path):
        logger.warning(f"Image path does not exist: {image_path}")
        return []
    
    try:
        reader = get_reader(gpu)
        results = reader.readtext(image_path)
        
        regions = []
        for bbox, text, confidence in results:
            # EasyOCR returns bbox as 4 corner points, convert to x1,y1,x2,y2
            x_coords = [p[0] for p in bbox]
            y_coords = [p[1] for p in bbox]
            
            regions.append(TextRegion(
                text=text,
                bbox=(int(min(x_coords)), int(min(y_coords)), 
                      int(max(x_coords)), int(max(y_coords))),
                confidence=confidence
            ))
        
        return regions
    except Exception as e:
        logger.error(f"OCR failed for {image_path}: {e}")
        return []  # Return empty list on failure - graceful degradation

