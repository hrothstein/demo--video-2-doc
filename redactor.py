"""
Apply blur/redaction to images at specified bounding boxes.
"""

from PIL import Image, ImageFilter, ImageDraw
from pii_detector import PIIMatch
import logging

logger = logging.getLogger(__name__)

def apply_redactions(
    image_path: str,
    output_path: str,
    pii_matches: list[PIIMatch],
    mode: str = 'blur'  # 'blur', 'black', 'pixelate'
) -> str:
    """
    Apply redactions to image and save to output path.
    
    Note: Redaction mode is global - applies to all frames and all PII matches.
    Users select one mode (blur/black/pixelate) that applies universally.
    
    Args:
        image_path: Source image
        output_path: Where to save redacted version
        pii_matches: List of PII matches with bounding boxes
        mode: Redaction style (global setting)
    
    Returns:
        Output path
    """
    try:
        img = Image.open(image_path)
        
        for match in pii_matches:
            bbox = match.region.bbox
            x1, y1, x2, y2 = bbox
            
            # Add padding around the detected region
            padding = 5
            x1 = max(0, x1 - padding)
            y1 = max(0, y1 - padding)
            x2 = min(img.width, x2 + padding)
            y2 = min(img.height, y2 + padding)
            
            if mode == 'blur':
                # Extract region, blur heavily, paste back
                region = img.crop((x1, y1, x2, y2))
                blurred = region.filter(ImageFilter.GaussianBlur(radius=15))
                img.paste(blurred, (x1, y1))
                
            elif mode == 'black':
                # Draw black rectangle
                draw = ImageDraw.Draw(img)
                draw.rectangle([x1, y1, x2, y2], fill='black')
                
            elif mode == 'pixelate':
                # Pixelate by scaling down then up
                region = img.crop((x1, y1, x2, y2))
                small = region.resize((8, 8), Image.BILINEAR)
                pixelated = small.resize(region.size, Image.NEAREST)
                img.paste(pixelated, (x1, y1))
        
        img.save(output_path, quality=90)
        return output_path
    except Exception as e:
        logger.error(f"Failed to apply redactions to {image_path}: {e}")
        raise


def generate_preview(
    image_path: str,
    output_path: str,
    pii_matches: list[PIIMatch]
) -> str:
    """
    Generate preview image with red boxes around detected PII.
    Does NOT apply actual redaction — just shows what will be redacted.
    """
    try:
        img = Image.open(image_path)
        draw = ImageDraw.Draw(img)
        
        for match in pii_matches:
            bbox = match.region.bbox
            # Red box with label
            draw.rectangle(bbox, outline='red', width=3)
            draw.text(
                (bbox[0], bbox[1] - 15),
                match.pii_type,
                fill='red'
            )
        
        img.save(output_path, quality=90)
        return output_path
    except Exception as e:
        logger.error(f"Failed to generate preview for {image_path}: {e}")
        raise

