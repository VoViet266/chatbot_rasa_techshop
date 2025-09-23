def format_vnd(amount):
    try:
        # Định dạng số có dấu phẩy ngăn cách hàng nghìn
        formatted_amount = f"{amount:,.0f}"
        
        # Thay thế dấu phẩy (,) thành dấu chấm (.) cho định dạng tiếng Việt
        formatted_amount = formatted_amount.replace(",", ".")
        return f"{formatted_amount} VNĐ"
    except (ValueError, TypeError):
        return "Giá trị không hợp lệ"
    
print(format_vnd(100000000))