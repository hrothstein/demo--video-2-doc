"""
Detect PII in extracted text regions.
"""

import re
from dataclasses import dataclass
from ocr_engine import TextRegion
import logging

logger = logging.getLogger(__name__)

@dataclass
class PIIMatch:
    region: TextRegion
    pii_type: str
    confidence: str  # 'high' or 'medium'
    matched_text: str

# High-confidence patterns (always applied)
PII_PATTERNS = {
    'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    'phone': r'(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
    'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
    'credit_card': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
    'ip_address': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
    'user_path_unix': r'/Users/[A-Za-z0-9_-]+',
    'user_path_windows': r'C:\\Users\\[A-Za-z0-9_-]+',
    'aws_key': r'\b(AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}\b',
    'api_key_openai': r'\bsk-[A-Za-z0-9]{32,}\b',
    'api_key_github': r'\bghp_[A-Za-z0-9]{36}\b',
}

# Optional patterns (user must enable)
OPTIONAL_PATTERNS = {
    'url': r'https?://[^\s<>"{}|\\^`\[\]]+',
    'date': r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
}

def luhn_check(card_number: str) -> bool:
    """
    Validate credit card number using Luhn algorithm.
    Reduces false positives from random 16-digit numbers.
    """
    # Remove non-digits
    digits = [int(d) for d in card_number if d.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    
    checksum = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    
    return checksum % 10 == 0

def detect_pii(
    regions: list[TextRegion],
    enable_optional: list[str] = None
) -> list[PIIMatch]:
    """
    Scan text regions for PII patterns.
    
    Args:
        regions: List of TextRegion from OCR
        enable_optional: List of optional pattern names to enable
    
    Returns:
        List of PIIMatch with detected PII
    """
    enable_optional = enable_optional or []
    matches = []
    
    # Combine patterns
    active_patterns = dict(PII_PATTERNS)
    for name in enable_optional:
        if name in OPTIONAL_PATTERNS:
            active_patterns[name] = OPTIONAL_PATTERNS[name]
    
    for region in regions:
        for pii_type, pattern in active_patterns.items():
            found = re.findall(pattern, region.text, re.IGNORECASE)
            if found:
                matched_text = found[0] if isinstance(found[0], str) else found[0][0]
                
                # Additional validation for credit cards
                if pii_type == 'credit_card':
                    # Remove spaces/dashes for Luhn check
                    card_digits = ''.join(c for c in matched_text if c.isdigit())
                    if not luhn_check(card_digits):
                        continue  # Skip if Luhn check fails
                
                matches.append(PIIMatch(
                    region=region,
                    pii_type=pii_type,
                    confidence='high' if pii_type in PII_PATTERNS else 'medium',
                    matched_text=matched_text
                ))
    
    return matches


def detect_names_ner(regions: list[TextRegion]) -> list[PIIMatch]:
    """
    Use spaCy NER to detect person names.
    Separate function due to higher false-positive rate.
    """
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
    except Exception as e:
        logger.warning(f"spaCy not available for name detection: {e}")
        return []  # spaCy not installed or model missing
    
    matches = []
    
    for region in regions:
        try:
            doc = nlp(region.text)
            for ent in doc.ents:
                if ent.label_ == "PERSON":
                    matches.append(PIIMatch(
                        region=region,
                        pii_type='person_name',
                        confidence='medium',
                        matched_text=ent.text
                    ))
        except Exception as e:
            logger.warning(f"spaCy NER failed for text '{region.text}': {e}")
            continue
    
    return matches

