thonimport re
from typing import Any, Optional

def clean_text(value: Any) -> str:
    """
    Normalize whitespace and strip leading/trailing spaces from text.
    """
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def parse_price(value: Any) -> Optional[float]:
    """
    Parse price strings like '€230.000', '230.000 €', '€230,000' into numeric value.
    """
    if value is None:
        return None
    text = clean_text(value)
    if not text:
        return None

    # Remove currency symbols and spaces
    text = re.sub(r"[^\d,\.]", "", text)

    # Handle Italian style 230.000 or 230.000,00
    if "," in text and "." in text:
        # Assume '.' is thousands separator and ',' is decimal
        text = text.replace(".", "").replace(",", ".")
    elif "," in text and "." not in text:
        # Either thousands or decimal; we assume decimal for safety
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", "")

    try:
        return float(text)
    except ValueError:
        return None

def parse_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"(-?\d+)", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None

def parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = clean_text(value)
    if not text:
        return None
    text = text.replace(",", ".")
    match = re.search(r"(-?\d+(?:\.\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None