
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from typing import Any, Text, Dict, List
from bson import ObjectId
from utils.database import DatabaseService
from utils.order_helpers import (
    format_status,
    build_order_card_html,
    build_orders_summary_header
)


def _validate_user(tracker: Tracker, dispatcher: CollectingDispatcher):
    """Validate user_id từ tracker"""
    user_id = tracker.sender_id
    if not user_id:
        dispatcher.utter_message(text="Vui lòng đăng nhập để xem đơn hàng.")
        return None
    return user_id


class ActionListAllOrders(Action):
    """
    Action để hiển thị toàn bộ đơn hàng của user
    Khi user hỏi chung chung như "thông tin đơn hàng của tôi", "xem tất cả đơn hàng"
    """
    
    def name(self) -> Text:
        return "action_list_all_orders"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Validate user
        user_id = _validate_user(tracker, dispatcher)
        if not user_id:
            return []
        
        db = DatabaseService()
        try:
            orders = list(db.orders_collection.find({"user": ObjectId(user_id) }).sort("createdAt", -1)) 
            if not orders:
                dispatcher.utter_message(text="Bạn chưa có đơn hàng nào!!")
                return []
            
            # Tạo thống kê
            total_orders = len(orders)
            total_spent = sum(order.get('totalPrice', 0) for order in orders)
            
            # Thống kê trạng thái
            status_count = {}
            for order in orders:
                status = format_status(order.get('status', 'pending'))
                status_count[status] = status_count.get(status, 0) + 1
            
            # Build header với thống kê
            header_html = build_orders_summary_header(total_orders, total_spent, status_count)
            
            # Limit to latest 10 orders for display
            display_orders = orders[:10]
            
            # Build HTML for each order
            html_parts = [header_html]
            for order in display_orders:
                html_parts.append(build_order_card_html(order, db.products_collection))
            
            # Add footer if there are more than 10 orders
            if total_orders > 10:
                footer_html = f"""
                <div style="
                    text-align: center;
                    padding: 12px;
                    color: #666;
                    font-size: 13px;
                    font-style: italic;
                ">
                    Đang hiển thị 10 đơn hàng gần nhất. 
                    Bạn có tổng {total_orders} đơn hàng.
                </div>
                """
                html_parts.append(footer_html)
            
            dispatcher.utter_message(text="\n".join(html_parts))
            return []
            
        except Exception as e:
            print(f"Error in ActionListAllOrders: {e}")
            dispatcher.utter_message(text="Đã có lỗi xảy ra khi lấy thông tin đơn hàng. 😔")
            return []
