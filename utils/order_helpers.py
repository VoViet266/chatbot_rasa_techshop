

from typing import Dict
from datetime import datetime


def format_status(status: str) -> str:
    """Format status cho user-friendly display"""
    status_map = {
        "PENDING": "Chờ xác nhận",
        "CONFIRMED": "Đã xác nhận",
        "PROCESSING": "Đang xử lý",
        "SHIPPING": "Đang giao",
        "DELIVERED": "Đã giao",
        "COMPLETED": "Hoàn thành", 
        "CANCELLED": "Đã hủy",
        "PENDING_PAYMENT": "Chờ thanh toán",
        "PAID": "Đã thanh toán",
    }
    return status_map.get(status, status)


def build_order_card_html(order: Dict, products_coll) -> str:
    """
    Build beautiful HTML card for displaying a single order
    Used by both action_check_order and action_list_all_orders
    """
    order_id = str(order.get('_id', ''))
    status = format_status(order.get('status', ''))
    total = order.get('totalPrice', 0)
    created_at = order.get('createdAt', datetime.now()).strftime('%d/%m/%Y %H:%M')
    
    # Get products
    products_html = ""
    for item in order.get('items', []):
        product_id = item.get('product')
        product_info = products_coll.find_one({"_id": product_id})
        product_name = product_info.get('name', 'Sản phẩm')
        quantity = item.get('quantity', 1)
        price = item.get('price', 0)
        products_html += f"""
        <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0f0f0;">
            <div style="flex: 1;">
                <div style="font-weight: 500; color: #333;">{product_name}</div>
                <div style="font-size: 12px; color: #888;">Số lượng: {quantity}</div>
            </div>
            <div style="font-weight: 600; color: #d32f2f;">{price:,.0f}₫</div>
        </div>
        """
    
    html = f"""
    <div style="
        border: 1px solid #e0e0e0; 
        border-radius: 12px; 
        padding: 16px; 
        margin: 10px 0; 
        background: #fff;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; max-width: 350px; min-width: 350px;">
            <div>
                <div style="font-size: 11px; color: #888; margin-bottom: 4px;">MÃ ĐƠN HÀNG</div>
                <div style="font-weight: 600; color: #333; font-size: 14px;">{order_id}</div>
            </div>
            <div style="
                color: #d32f2f; 
                padding: 6px 12px; 
                border-radius: 20px; 
                font-size: 12px; 
                font-weight: 600;
            ">{status}</div>
        </div>
        
        <!-- Order Date -->
        <div style="font-size: 12px; color: #666; margin-bottom: 12px;">
            <span style="color: #888;">📅</span> {created_at}
        </div>
        
        <!-- Products List -->
        <div style="margin: 12px 0;">
            {products_html}
        </div>
        
        <!-- Total -->
        <div style="
            display: flex; 
            justify-content: space-between; 
            align-items: center;
            padding-top: 12px;
            border-top: 2px solid #f0f0f0;
            margin-top: 8px;
        ">
            <div style="font-weight: 600; color: #333; font-size: 14px;">Tổng tiền:</div>
            <div style="font-weight: 700; color: #d32f2f; font-size: 18px;">{total:,.0f}₫</div>
        </div>
    </div>
    """
    return html


def build_orders_summary_header(total_orders: int, total_spent: float, status_count: Dict[str, int]) -> str:
    """
    Build summary header for list of orders
    Used by action_list_all_orders
    """
    # Build status summary
    status_summary = ", ".join([f"{count} {status}" for status, count in status_count.items()])
    
    header_html = f"""
    <div style="
        background: linear-gradient(135deg, #d32f2f 0%, #f44336 100%);
        color: white;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 16px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(211, 47, 47, 0.3);
    ">
        <div style="font-size: 24px; font-weight: 700; margin-bottom: 8px;">📦 Tất cả đơn hàng</div>
        <div style="font-size: 14px; opacity: 0.95;">
            <div style="margin-bottom: 4px;">Tổng: <strong>{total_orders}</strong> đơn hàng</div>
            <div style="margin-bottom: 4px;">Tổng chi tiêu: <strong>{total_spent:,.0f}₫</strong></div>
            <div style="font-size: 12px; opacity: 0.9;">{status_summary}</div>
        </div>
    </div>
    """
    return header_html


def build_filter_info_header(filter_desc: str, count: int) -> str:
    """
    Build header showing filter information
    Used by action_check_order when filters are applied
    """
    header_html = f"""
    <div style="
        background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%);
        color: white;
        padding: 16px;
        border-radius: 10px;
        margin-bottom: 12px;
        text-align: center;
        box-shadow: 0 3px 10px rgba(33, 150, 243, 0.3);
    ">
        <div style="font-size: 18px; font-weight: 600; margin-bottom: 4px;">🔍 {filter_desc}</div>
        <div style="font-size: 13px; opacity: 0.9;">Tìm thấy <strong>{count}</strong> đơn hàng</div>
    </div>
    """
    return header_html
