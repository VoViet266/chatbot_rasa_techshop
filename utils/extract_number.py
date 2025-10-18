import re

def extract_number(text_string):
    if not isinstance(text_string, str):
        return None
    pattern = r"(\d+\.?\d*)"
    
    match = re.search(pattern, text_string)
    
    if match:
        number_str = match.group(1)
        try:
            return int(number_str)
        except ValueError:
            return None
    
    return None