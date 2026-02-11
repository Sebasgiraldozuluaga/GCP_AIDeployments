import re

def sanitize_text_for_json(text: str) -> str:
    """Sanitize text to be safely included in JSON."""
    if not text:
        return ""
    
    # Replace problematic characters
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Remove any null bytes
    text = text.replace('\x00', '')
    # Convert literal \n sequences to actual newlines
    text = text.replace('\\n', '\n')
    text = text.replace('\\t', '\t')
    
    # Also handle cases where LLM outputs literal backslash-n in different encodings
    text = re.sub(r'(?<!\\)\\n', '\n', text)
    # Clean up any double newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove other control characters
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text

def sanitize_dict_for_json(obj):
    """Recursively sanitize all strings in a dict/list for JSON."""
    if isinstance(obj, dict):
        return {k: sanitize_dict_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_dict_for_json(item) for item in obj]
    elif isinstance(obj, str):
        return sanitize_text_for_json(obj)
    else:
        return obj

def to_colombian_monetary_format(num_value: float) -> str:
    """Convert a number to Colombian format (dots for thousands, no decimals)."""
    rounded = round(num_value)
    return f"{rounded:,}".replace(',', '.')

def format_monetary_values_in_text(text: str) -> str:
    """
    Format monetary values in text to Colombian format.
    Handles American format and raw decimals.
    """
    # Pattern 1: American format (e.g., "293,189,026.58" or "1,234,567")
    pattern_american = r'\b(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?)\b'
    
    def replace_american(match):
        try:
            num = float(match.group(0).replace(',', ''))
            return to_colombian_monetary_format(num)
        except ValueError:
            return match.group(0)
    
    text = re.sub(pattern_american, replace_american, text)
    
    # Pattern 2: Raw decimal numbers (e.g., "53402979.67")
    pattern_decimal = r'\b(\d{4,})\.(\d{1,2})\b'
    
    def replace_decimal(match):
        try:
            num = float(match.group(0))
            return to_colombian_monetary_format(num)
        except ValueError:
            return match.group(0)
    
    text = re.sub(pattern_decimal, replace_decimal, text)
    
    # Pattern 3: Large integers in context (e.g., "Total: 53402979")
    pattern_large_int = r'(\d{4,})(?=\s|$|\.(?!\d)|,(?!\d))'
    
    def replace_large_int(match):
        try:
            num = float(match.group(1))
            return to_colombian_monetary_format(num)
        except ValueError:
            return match.group(0)
    
    return re.sub(pattern_large_int, replace_large_int, text)
