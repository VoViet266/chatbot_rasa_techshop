from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from bson import ObjectId
from utils.database import DatabaseService


class ActionViewCart(Action):
    def name(self) -> str:
        return "action_view_cart"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        # Lấy user_id
        user_id = tracker.sender_id

        # 1. Kiểm tra đăng nhập
        if not user_id or not ObjectId.is_valid(user_id):
            dispatcher.utter_message(
                text="Quý khách vui lòng đăng nhập để sử dụng dịch vụ."
            )
            return []

        db_service = DatabaseService()
        cart = db_service.carts_collection.find_one({"user": ObjectId(user_id)})

        # Nếu không có giỏ hàng hoặc bị xóa
        if not cart or cart.get("isDeleted", False):
            dispatcher.utter_message(text="Giỏ hàng của bạn hiện đang trống.")
            return []

        items = cart.get("items", [])
        if not items:
            dispatcher.utter_message(text="Giỏ hàng của bạn hiện đang trống.")
            return []

        message_lines = ["Giỏ hàng của bạn:"]
        for item in items:
            color = item.get("color", "")
            quantity = item.get("quantity", 1)
            price = item.get("price", 0)
            subtotal = quantity * price

            # Nếu có nhiều variant hoặc màu thì ghi rõ
            detail = f" (Màu: {color})" if color else ""
            message_lines.append(f"- Sản phẩm {detail} x{quantity}: {subtotal:,}₫")

        total_price = cart.get("totalPrice", 0)
        total_quantity = cart.get("totalQuantity", len(items))
        message_lines.append(f"\nTổng số lượng: {total_quantity}")
        message_lines.append(f"Tổng cộng: {total_price:,}₫")

        dispatcher.utter_message(text="\n".join(message_lines))
        return []
