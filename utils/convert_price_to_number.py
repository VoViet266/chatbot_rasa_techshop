import re

def convert_price_to_number(price_text):
    """Convert price text to integer number in VND
    Examples:
    - "15 triệu" -> 15000000
    - "15 nghìn" -> 15000
    - "15" -> 15
    """
    number = float(re.findall(r'\d+', price_text)[0])
    if 'triệu' in price_text.lower():
        return int(number * 1000000)
    elif 'nghìn' in price_text.lower():
        return int(number * 1000)
    return int(number)