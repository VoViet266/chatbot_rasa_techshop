import re


def format_vnd(amount):
    """Format a number or numeric-like string to Vietnamese VND format.

    Examples:
      format_vnd(1000000) -> '1.000.000 VNĐ'
      format_vnd('1,000,000') -> '1.000.000 VNĐ'
    """
    try:
        if amount is None:
            raise ValueError("None is not a valid amount")

        s = str(amount).strip()

        # Remove any non-numeric characters except dot and minus
        s = re.sub(r"[^0-9\.\-]", "", s)

        # If there are multiple dots, assume they are thousand separators and remove them
        if s.count('.') > 1 and s.count(',') == 0:
            s = s.replace('.', '')

        # Remove any remaining commas (thousands separators)
        s = s.replace(',', '')

        # Convert to float then to integer (VND has no fractional units here)
        value = float(s)
        value_int = int(round(value))

        # Format with thousand separator, then convert comma -> dot for VN style
        formatted_amount = f"{value_int:,}"
        formatted_amount = formatted_amount.replace(",", ".")
        return f"{formatted_amount} VNĐ"
    except Exception:
        return "Giá trị không hợp lệ"