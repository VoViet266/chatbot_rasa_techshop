"""
Unified Order Actions
Gộp 4 actions: check_order_specific, check_order_general, check_order_filter, check_order_by_product
thành 1 action: action_check_order
"""

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from bson import ObjectId
from bson.errors import InvalidId
from typing import Any, Text, Dict, List
from datetime import datetime, timedelta
import dateparser
from utils.database import DatabaseService


def _validate_user(tracker: Tracker, dispatcher: CollectingDispatcher):
    """Validate user_id từ tracker"""
    user_id = tracker.sender_id
    if not user_id:
        dispatcher.utter_message(text="Vui lòng đăng nhập để xem đơn hàng.")
        return None
    return user_id


def _map_status_to_db(status_nlu: str):
    """Map status từ NLU sang database values"""
    mapping = {
        "đang giao": ["shipping", "delivering"],
        "đã giao": ["delivered", "completed"],
        "đang xử lý": ["processing", "confirmed"],
        "đã huỷ": ["cancelled"],
        "chờ thanh toán": ["pending_payment", "unpaid"],
        "đã thanh toán": ["paid"],
        "chờ xác nhận": ["pending", "waiting_confirmation"],
        "pending": ["pending", "waiting_confirmation"],
        "completed": ["delivered", "completed"],
        "cancelled": ["cancelled"],
    }
    return mapping.get(status_nlu.lower(), [status_nlu])


def _get_time_query(time_str: str):
    """Parse time string và tạo MongoDB query"""
    if not time_str:
        return {}
    
    time_str_lower = time_str.lower().strip()
    now = datetime.now()
    
    # Map common time phrases
    time_mapping = {
        "hôm nay": (now.replace(hour=0, minute=0, second=0), now.replace(hour=23, minute=59, second=59)),
        "hôm qua": ((now - timedelta(days=1)).replace(hour=0, minute=0, second=0),
                   (now - timedelta(days=1)).replace(hour=23, minute=59, second=59)),
        "tuần này": (now - timedelta(days=now.weekday()), now),
        "tuần trước": (now - timedelta(days=now.weekday() + 7), now - timedelta(days=now.weekday())),
        "tháng này": (now.replace(day=1), now),
        "tháng trước": ((now.replace(day=1) - timedelta(days=1)).replace(day=1), now.replace(day=1)),
        "năm nay": (now.replace(month=1, day=1), now),
    }
    
    # Check exact matches
    if time_str_lower in time_mapping:
        start_time, end_time = time_mapping[time_str_lower]
        return {"createdAt": {"$gte": start_time, "$lte": end_time}}
    
    # Handle "X ngày trước", "X ngày qua"
    if "ngày" in time_str_lower:
        try:
            days = int(''.join(filter(str.isdigit, time_str)))
            start_time = now - timedelta(days=days)
            return {"createdAt": {"$gte": start_time, "$lte": now}}
        except:
            pass
    
    # Try dateparser
    try:
        parsed_date = dateparser.parse(time_str, languages=['vi'])
        if parsed_date:
            start = parsed_date.replace(hour=0, minute=0, second=0)
            end = parsed_date.replace(hour=23, minute=59, second=59)
            return {"createdAt": {"$gte": start, "$lte": end}}
    except:
        pass
    
    return {}


def _format_status(status: str) -> str:
    """Format status cho user-friendly display"""
    status_map = {
        "pending": "Chờ xác nhận",
        "confirmed": "Đã xác nhận",
        "processing": "Đang xử lý",
        "shipping": "Đang giao",
        "delivered": "Đã giao",
        "completed": "Hoàn thành", 
        "cancelled": "Đã hủy",
        "pending_payment": "Chờ thanh toán",
        "paid": "Đã thanh toán",
    }
    return status_map.get(status, status)


def build_order_html(order: Dict, products_coll):
    """Build HTML for displaying order"""
    order_id = str(order.get('_id', ''))
    status = _format_status(order.get('status', ''))
    total = order.get('totalPrice', 0)
    created_at = order.get('createdAt', datetime.now()).strftime('%d/%m/%Y %H:%M')
    
    # Get products
    products_html = ""
    for item in order.get('products', []):
        product_info = products_coll.find_one({"_id": item.get('productId')})
        product_name = product_info.get('name', 'Sản phẩm') if product_info else 'Sản phẩm'
        quantity = item.get('quantity', 1)
        price = item.get('price', 0)
        products_html += f"<li>{product_name} x{quantity} - {price:,.0f}₫</li>"
    
    html = f"""
    <div style="border: 1px solid #ddd; padding: 10px; margin: 5px 0; border-radius: 5px;">
        <div><strong>Mã đơn:</strong> {order_id}</div>
        <div><strong>Trạng thái:</strong> {status}</div>
        <div><strong>Ngày đặt:</strong> {created_at}</div>
        <div><strong>Sản phẩm:</strong></div>
        <ul>{products_html}</ul>
        <div><strong>Tổng tiền:</strong> {total:,.0f}₫</div>
    </div>
    """
    return html


class ActionCheckOrder(Action):
    """
    Unified action để xử lý TẤT CẢ các loại query về đơn hàng:
    - Theo order_id cụ thể
    - Theo order_direction + order_index (mới nhất, thứ 2, thứ 3...)
    - Theo time (hôm nay, tuần này, tháng trước...)
    - Theo order_status (đang giao, đã giao, chờ thanh toán...)
    - Theo product_name (đơn có sản phẩm X)
    - Kết hợp nhiều filters
    """
    
    def name(self) -> Text:
        return "action_check_order"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Validate user
        user_id = _validate_user(tracker, dispatcher)
        if not user_id:
            return []
        
        db = DatabaseService()
        
        # Get all possible slots
        order_id = tracker.get_slot("order_id")
        order_direction = tracker.get_slot("order_direction")  # newest/oldest
        order_index = tracker.get_slot("order_index")  # 1, 2, 3...
        time_str = tracker.get_slot("time")
        order_status = tracker.get_slot("order_status")
        product_name = tracker.get_slot("product_name")
        order_limit = tracker.get_slot("order_limit")
        
        # Build query
        query = {"userId": user_id}
        
        # 1. ORDER_ID cụ thể (ưu tiên cao nhất)
        if order_id:
            try:
                if ObjectId.is_valid(order_id):
                    query["_id"] = ObjectId(order_id)
                else:
                    dispatcher.utter_message(text=f"Mã đơn hàng '{order_id}' không hợp lệ.")
                    return []
            except InvalidId:
                dispatcher.utter_message(text=f"Mã đơn hàng '{order_id}' không hợp lệ.")
                return []
        
        # 2. TIME filter
        if time_str:
            time_query = _get_time_query(time_str)
            query.update(time_query)
        
        # 3. STATUS filter
        if order_status:
            status_values = _map_status_to_db(order_status)
            query["status"] = {"$in": status_values}
        
        # 4. PRODUCT filter
        if product_name:
            # Find product
            product = db.products_collection.find_one(
                {"name": {"$regex": product_name, "$options": "i"}}
            )
            if product:
                query["products.productId"] = product["_id"]
            else:
                dispatcher.utter_message(text=f"Không tìm thấy sản phẩm '{product_name}'.")
                return []
        
        # Execute query
        try:
            # Sort
            sort_direction = -1 if order_direction == "newest" or not order_direction else 1
            
            orders = list(db.orders_collection.find(query).sort("createdAt", sort_direction))
            
            if not orders:
                dispatcher.utter_message(text="Không tìm thấy đơn hàng nào phù hợp.")
                return []
            
            # 5. Apply ORDER_INDEX (nếu có)
            if order_index:
                try:
                    index = int(order_index) - 1  # Convert to 0-based
                    if 0 <= index < len(orders):
                        orders = [orders[index]]
                    else:
                        dispatcher.utter_message(text=f"Không tìm thấy đơn hàng thứ {order_index}.")
                        return []
                except ValueError:
                    pass
            
            # 6. Apply LIMIT
            if order_limit and not order_index:
                try:
                    if isinstance(order_limit, (int, float)):
                        limit = int(order_limit)
                    else:
                        # Handle "vài", "một số", "tất cả"
                        limit_map = {
                            "vài": 3,
                            "một số": 5,
                            "tất cả": 999,
                        }
                        limit = limit_map.get(str(order_limit).lower(), 5)
                    orders = orders[:limit]
                except:
                    orders = orders[:5]
            elif not order_index:
                # Default limit
                orders = orders[:5]
            
            # Build response
            if len(orders) == 1:
                html = build_order_html(orders[0], db.products_collection)
                dispatcher.utter_message(text=html)
            else:
                intro = f"Tìm thấy {len(orders)} đơn hàng:"
                html_parts = [intro]
                for order in orders:
                    html_parts.append(build_order_html(order, db.products_collection))
                dispatcher.utter_message(text="\n".join(html_parts))
            
            return []
            
        except Exception as e:
            print(f"Error in ActionCheckOrder: {e}")
            dispatcher.utter_message(text="Đã có lỗi xảy ra khi tìm đơn hàng.")
            return []


class ActionCheckPendingOrders(Action):
    """
    Action để xử lý đơn hàng CHƯA HOÀN THÀNH:
    - Chưa thanh toán (unpaid/pending_payment)
    - Đang giao (shipping/delivering)
    - Chưa giao (chưa nhận)
    """
    
    def name(self) -> Text:
        return "action_check_pending_orders"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Validate user
        user_id = _validate_user(tracker, dispatcher)
        if not user_id:
            return []
        
        db = DatabaseService()
        
        # Query for pending orders (all non-completed statuses)
        query = {
            "userId": user_id,
            "status": {
                "$in": ["pending", "confirmed", "processing", "shipping", 
                       "pending_payment", "unpaid", "delivering"]
            }
        }
        
        try:
            orders = list(db.orders_collection.find(query).sort("createdAt", -1))
            
            if not orders:
                dispatcher.utter_message(text="Bạn không có đơn hàng nào đang chờ xử lý.")
                return []
            
            intro = f"Bạn có {len(orders)} đơn hàng đang chờ:"
            html_parts = [intro]
            for order in orders:
                html_parts.append(build_order_html(order, db.products_collection))
            
            dispatcher.utter_message(text="\n".join(html_parts))
            return []
            
        except Exception as e:
            print(f"Error in ActionCheckPendingOrders: {e}")
            dispatcher.utter_message(text="Đã có lỗi xảy ra khi tìm đơn hàng.")
            return []
