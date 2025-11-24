from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from bson import ObjectId
from datetime import datetime, timedelta
import dateparser
from utils.database import DatabaseService
from utils.validate_user import _validate_user
from utils.order_helpers import build_order_card_html, build_filter_info_header

def _map_status_to_db(status_vn: str) -> str:
    """Map Vietnamese status to DB status code"""
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
    if not time_str:
        return {}
        
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    time_lower = time_str.lower()
    
    time_ranges = {
        ("hôm nay", "nay"): {"$gte": today_start},
        ("hôm qua",): {
            "$gte": today_start - timedelta(days=1),
            "$lt": today_start
        },
        ("tuần này",): {
            "$gte": today_start - timedelta(days=today_start.weekday())
        },
        ("tháng này",): {
            "$gte": today_start.replace(day=1)
        }
    }
    
    for keys, query in time_ranges.items():
        if time_lower in keys:
            return query
    
    # Try parsing date
    try:
        parsed_date = dateparser.parse(time_str)
        if parsed_date:
            start_day = parsed_date.replace(hour=0, minute=0, second=0, microsecond=0)
            return {"$gte": start_day, "$lt": start_day + timedelta(days=1)}
    except Exception:
        pass
        
    return {}


class ActionCheckOrder(Action):
    def name(self) -> Text:
        return "action_check_order"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Validate user
        user_id = _validate_user(tracker, dispatcher, message="Vui lòng đăng nhập để xem đơn hàng!")
        if not user_id:
            return []
        
        # Get slots
        order_id = tracker.get_slot("order_id")
        order_direction = tracker.get_slot("order_direction")
        order_index = tracker.get_slot("order_index")
        time_str = tracker.get_slot("time")
        order_status = tracker.get_slot("order_status")
        product_name = tracker.get_slot("product_name")
        
        db = DatabaseService()
        query = {"user": ObjectId(user_id)}
        
        # Build query filters
        if order_id:
            query["_id"] = ObjectId(order_id)
        
        if order_status:
            db_status = _map_status_to_db(order_status)
            if db_status:
                query["status"] = db_status
        
        if time_str:
            time_query = _get_time_query(time_str)
            if time_query:
                query["createdAt"] = time_query
        
        if product_name:
            products = list(db.products_collection.find(
                {"name": {"$regex": product_name, "$options": "i"}},
                {"_id": 1}
            ))
            if products:
                query["items.product"] = {"$in": [p["_id"] for p in products]}
            else:
                dispatcher.utter_message(
                    text=f"Không tìm thấy sản phẩm '{product_name}'."
                )
                return []
        
        # Execute query
        try:
            sort_direction = 1 if order_direction == "oldest" else -1
            orders = list(db.orders_collection.find(query).sort("createdAt", sort_direction))
            
            if not orders:
                dispatcher.utter_message(response="utter_no_orders_found")
                return []
            
            # Handle specific index
            if order_index:
                try:
                    idx = int(order_index) - 1
                    if 0 <= idx < len(orders):
                        orders = [orders[idx]]
                    else:
                        dispatcher.utter_message(
                            text=f"Không tìm thấy đơn hàng thứ {order_index}."
                        )
                        return []
                except ValueError:
                    pass
            
            # Limit results
            if not order_id and len(orders) > 5:
                orders = orders[:5]
            
            # Display results
            if len(orders) == 1:
                html = build_order_card_html(orders[0], db.products_collection)
                dispatcher.utter_message(text=html)
            else:
                # Determine filter description
                if time_str:
                    filter_desc = f"Đơn hàng {time_str}"
                elif order_status:
                    filter_desc = f"Đơn hàng {order_status}"
                elif order_direction == "newest":
                    filter_desc = "Đơn hàng mới nhất"
                else:
                    filter_desc = "Kết quả tìm kiếm"
                
                header = build_filter_info_header(filter_desc, len(orders))
                html_parts = [header] + [
                    build_order_card_html(order, db.products_collection)
                    for order in orders
                ]
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
        
        # Query pending orders
        query = {
            "user": ObjectId(user_id),
            "status": {"$in": ["PENDING", "CONFIRMED", "PROCESSING", 
                              "SHIPPING", "PENDING_PAYMENT"]}
        }
        
        try:
            orders = list(db.orders_collection.find(query).sort("createdAt", -1))
            
            if not orders:
                dispatcher.utter_message(
                    text="Bạn không có đơn hàng nào đang chờ xử lý."
                )
                return []
            
            # Build header
            header = build_filter_info_header(
                "⏳ Đơn hàng đang chờ",
                len(orders),
                border_color="#f59e0b"
            )
            
            html_parts = [header] + [
                build_order_card_html(order, db.products_collection)
                for order in orders
            ]
            
            dispatcher.utter_message(text="\n".join(html_parts))
            
        except Exception as e:
            print(f"Error in ActionCheckPendingOrders: {e}")
            dispatcher.utter_message(text="Có lỗi xảy ra khi kiểm tra đơn hàng.")
            
        return []
