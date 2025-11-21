from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from bson import ObjectId, InvalidId
from datetime import datetime, timedelta
import dateparser
from utils.database import DatabaseService
from utils.order_helpers import (
    build_order_card_html,
    build_filter_info_header
)


def _validate_user(tracker: Tracker, dispatcher: CollectingDispatcher):
    """Validate user_id từ tracker"""
    user_id = tracker.sender_id
    if not user_id:
        dispatcher.utter_message(text="Vui lòng đăng nhập để xem đơn hàng.")
        return None
    return user_id


def _map_status_to_db(status_vn: str) -> str:
    """Map Vietnamese status to DB status code (UPPERCASE)"""
    status_map = {
        "chờ xác nhận": "PENDING",
        "đã xác nhận": "CONFIRMED",
        "đang xử lý": "PROCESSING",
        "đang giao": "SHIPPING",
        "đã giao": "DELIVERED",
        "hoàn thành": "COMPLETED",
        "đã hủy": "CANCELLED",
        "chờ thanh toán": "PENDING_PAYMENT",
        "đã thanh toán": "PAID"
    }
    return status_map.get(status_vn.lower(), None)


def _get_time_query(time_str: str) -> Dict:
    """Generate MongoDB query for time range"""
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if not time_str:
        return {}
        
    time_lower = time_str.lower()
    
    if time_lower in ["hôm nay", "nay"]:
        return {"$gte": today_start}
        
    elif time_lower in ["hôm qua"]:
        yesterday_start = today_start - timedelta(days=1)
        return {"$gte": yesterday_start, "$lt": today_start}
        
    elif time_lower in ["tuần này"]:
        start_week = today_start - timedelta(days=today_start.weekday())
        return {"$gte": start_week}
        
    elif time_lower in ["tuần trước"]:
        start_week = today_start - timedelta(days=today_start.weekday())
        start_last_week = start_week - timedelta(days=7)
        return {"$gte": start_last_week, "$lt": start_week}
        
    elif time_lower in ["tháng này"]:
        start_month = today_start.replace(day=1)
        return {"$gte": start_month}
        
    elif time_lower in ["tháng trước"]:
        start_month = today_start.replace(day=1)
        # First day of last month
        last_month = start_month - timedelta(days=1)
        start_last_month = last_month.replace(day=1)
        return {"$gte": start_last_month, "$lt": start_month}
        
    # Try parsing date
    try:
        parsed_date = dateparser.parse(time_str)
        if parsed_date:
            start_day = parsed_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_day = start_day + timedelta(days=1)
            return {"$gte": start_day, "$lt": end_day}
    except:
        pass
        
    return {}


class ActionCheckOrder(Action):
    def name(self) -> Text:
        return "action_check_order"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # 1. Validate User
        user_id = _validate_user(tracker, dispatcher)
        if not user_id:
            return []
            
        # 2. Get Slots
        order_id = tracker.get_slot("order_id")
        order_direction = tracker.get_slot("order_direction") # newest, oldest
        order_index = tracker.get_slot("order_index") # 1, 2, 3...
        time_str = tracker.get_slot("time")
        order_status = tracker.get_slot("order_status")
        product_name = tracker.get_slot("product_name")
        
        db = DatabaseService()
        query = {"user": ObjectId(user_id)}
        
        # 3. Build Query
        
        # Case A: Specific Order ID
        if order_id:
            try:
                query["_id"] = ObjectId(order_id)
            except InvalidId:
                dispatcher.utter_message(text=f"Mã đơn hàng '{order_id}' không hợp lệ.")
                return []
        
        # Case B: Filter by Status
        if order_status:
            db_status = _map_status_to_db(order_status)
            if db_status:
                query["status"] = db_status
            else:
                # Nếu không map được chính xác, thử tìm theo text (ít khi xảy ra nếu NLU tốt)
                pass
                
        # Case C: Filter by Time
        if time_str:
            time_query = _get_time_query(time_str)
            if time_query:
                query["createdAt"] = time_query
                
        # Case D: Filter by Product Name (Advanced)
        if product_name:
            # Find products matching name first
            products = list(db.products_collection.find(
                {"name": {"$regex": product_name, "$options": "i"}},
                {"_id": 1}
            ))
            if products:
                product_ids = [p["_id"] for p in products]
                query["items.product"] = {"$in": product_ids}
            else:
                dispatcher.utter_message(text=f"Không tìm thấy sản phẩm nào tên '{product_name}' trong hệ thống.")
                return []

        # 4. Execute Query & Sort
        # Default sort by newest
        sort_direction = -1 # DESC
        if order_direction == "oldest":
            sort_direction = 1 # ASC
            
        try:
            orders = list(db.orders_collection.find(query).sort("createdAt", sort_direction))
            
            if not orders:
                dispatcher.utter_message(response="utter_no_orders_found")
                return []
                
            # 5. Handle Index (e.g. "đơn thứ 2")
            if order_index:
                try:
                    idx = int(order_index) - 1
                    if 0 <= idx < len(orders):
                        orders = [orders[idx]]
                    else:
                        dispatcher.utter_message(text=f"Không tìm thấy đơn hàng thứ {order_index} theo yêu cầu.")
                        return []
                except ValueError:
                    pass
            
            # 6. Limit results if too many (unless specific ID requested)
            if not order_id and len(orders) > 5:
                orders = orders[:5]
            
            # 7. Display Results
            if len(orders) == 1:
                # Single order
                html = build_order_card_html(orders[0], db.products_collection)
                dispatcher.utter_message(text=html)
            else:
                # Multiple orders
                filter_desc = "Kết quả tìm kiếm"
                if time_str: filter_desc = f"Đơn hàng {time_str}"
                elif order_status: filter_desc = f"Đơn hàng {order_status}"
                elif order_direction == "newest": filter_desc = "Đơn hàng mới nhất"
                
                header = build_filter_info_header(filter_desc, len(orders))
                html_parts = [header]
                
                for order in orders:
                    html_parts.append(build_order_card_html(order, db.products_collection))
                
                dispatcher.utter_message(text="\n".join(html_parts))
                
        except Exception as e:
            print(f"Error in ActionCheckOrder: {e}")
            dispatcher.utter_message(text="Có lỗi xảy ra khi tra cứu đơn hàng.")
            
        return []


class ActionCheckPendingOrders(Action):
    def name(self) -> Text:
        return "action_check_pending_orders"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        user_id = _validate_user(tracker, dispatcher)
        if not user_id:
            return []
            
        db = DatabaseService()
        
        # Pending statuses (UPPERCASE)
        pending_statuses = ["PENDING", "CONFIRMED", "PROCESSING", "SHIPPING", "PENDING_PAYMENT"]
        
        query = {
            "user": ObjectId(user_id),
            "status": {"$in": pending_statuses}
        }
        
        try:
            orders = list(db.orders_collection.find(query).sort("createdAt", -1))
            
            if not orders:
                dispatcher.utter_message(text="Bạn không có đơn hàng nào đang chờ xử lý.")
                return []
            
            # Build header for pending orders (Manual HTML to match style)
            header_html = f"""
            <div style="
                border: 1px solid #e5e7eb;
                border-left: 3px solid #f59e0b;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 12px;
                background: #ffffff;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 500px;
            ">
                <div style="font-size: 16px; font-weight: 700; color: #111827; margin-bottom: 4px;">
                    ⏳ Đơn hàng đang chờ
                </div>
                <div style="font-size: 13px; color: #6b7280;">
                    Bạn có <strong style="color: #111827;">{len(orders)}</strong> đơn hàng đang xử lý
                </div>
            </div>
            """
            
            html_parts = [header_html]
            for order in orders:
                html_parts.append(build_order_card_html(order, db.products_collection))
            
            dispatcher.utter_message(text="\n".join(html_parts))
            return []
            
        except Exception as e:
            print(f"Error in ActionCheckPendingOrders: {e}")
            dispatcher.utter_message(text="Có lỗi xảy ra khi kiểm tra đơn hàng.")
            return []
