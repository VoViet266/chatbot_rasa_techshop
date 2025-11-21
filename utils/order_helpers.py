

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
    Build clean, simple HTML card for order - no colors, no badges
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
        product_name = product_info.get('name', 'Sản phẩm') if product_info else 'Sản phẩm'
        quantity = item.get('quantity', 1)
        price = item.get('price', 0)
        products_html += f"""
        <div style="padding: 8px 0; display: flex; justify-content: space-between;">
            <div style="color: #374151;">• {product_name} <span style="color: #9ca3af;">x{quantity}</span></div>
            <div style="color: #111827; font-weight: 500;">{price:,.0f}₫</div>
        </div>
        """
    
    html = f"""
    <div style="
        border: 1px solid #e5e7eb; 
        border-radius: 8px; 
        padding: 16px; 
        margin: 8px 0; 
        background: #ffffff;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        max-width: 500px;
    ">
        <!-- Header -->
        <div style="margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #f3f4f6;">
            <div style="display: flex; justify-content: space-between; align-items: baseline;">
                <div>
                    <div style="font-size: 11px; color: #9ca3af; text-transform: uppercase; margin-bottom: 4px;">Mã đơn hàng</div>
                    <div style="font-weight: 600; color: #111827;">#{order_id[:12]}...</div>
                </div>
                <div style="font-size: 13px; color: #6b7280;">
                    {status}
                </div>
            </div>
            <div style="font-size: 12px; color: #9ca3af; margin-top: 8px;">
                {created_at}
            </div>
        </div>
        
        <!-- Products -->
        <div style="padding: 12px 0; border-bottom: 1px solid #f3f4f6;">
            <div style="font-size: 11px; color: #9ca3af; text-transform: uppercase; margin-bottom: 8px;">Sản phẩm</div>
            {products_html}
        </div>
        
        <!-- Total -->
        <div style="padding-top: 12px; display: flex; justify-content: space-between; align-items: center;">
            <div style="font-weight: 600; color: #374151;">Tổng cộng</div>
            <div style="font-weight: 700; color: #111827; font-size: 18px;">{total:,.0f}₫</div>
        </div>
    </div>
    """
    return html


def build_orders_summary_header(total_orders: int, total_spent: float, status_count: Dict[str, int]) -> str:
    """
    Build simple summary header - no gradient, clean
    """
    # Build status summary
    status_items = []
    for status, count in status_count.items():
        status_items.append(f"{count} {status}")
    status_summary = " • ".join(status_items)
    
    header_html = f"""
    <div style="
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        background: #ffffff;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        max-width: 500px;
    ">
        <div style="margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #f3f4f6;">
            <div style="font-size: 18px; font-weight: 700; color: #111827; margin-bottom: 4px;">
                📦 Đơn hàng của tôi
            </div>
        </div>
        <div style="font-size: 13px; color: #6b7280; line-height: 1.6;">
            <div style="margin-bottom: 4px;">
                <strong style="color: #111827;">{total_orders}</strong> đơn hàng • 
                <strong style="color: #111827;">{total_spent:,.0f}₫</strong>
            </div>
            <div style="font-size: 12px; color: #9ca3af;">{status_summary}</div>
        </div>
    </div>
    """
    return header_html


def build_filter_info_header(filter_desc: str, count: int) -> str:
    """
    Build simple filter header - no gradient
    """
    header_html = f"""
    <div style="
        border: 1px solid #e5e7eb;
        border-left: 3px solid #3b82f6;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        background: #ffffff;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        max-width: 500px;
    ">
        <div style="font-size: 14px; font-weight: 600; color: #111827; margin-bottom: 4px;">
            🔍 {filter_desc}
        </div>
        <div style="font-size: 12px; color: #6b7280;">
            Tìm thấy {count} đơn hàng
        </div>
    </div>
    """
    return header_html
