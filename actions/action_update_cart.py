import requests
from rasa_sdk import Action, Tracker
from bson import ObjectId
from utils.database import DatabaseService
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, AllSlotsReset


class ActionUpdateCart(Action):
    def name(self) -> str:
        return "action_update_cart"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
    ) -> list[SlotSet]:
        # 1. Lấy thông tin từ tracker
        product_name = tracker.get_slot("product_name")  # Tên sản phẩm muốn cập nhật
        intent_name = tracker.latest_message.get("intent", {}).get(
            "name"
        )  # Lấy intent (tăng hay giảm)
        user_id = tracker.sender_id
        metadata = tracker.latest_message.get("metadata", {})
        token = metadata.get("accessToken")

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

        # Nếu người dùng chưa cung cấp thông tin sản phẩm
        if not product_name:
            dispatcher.utter_message(
                text="Bạn vui lòng cho biết tên sản phẩm cần cập nhật!"
            )
            return []

        items = cart.get("items", [])
        if not items:
            dispatcher.utter_message(text="Giỏ hàng của bạn hiện đang trống.")
            return []

        # Mặc định thay đổi là 1
        quantity_change = tracker.get_slot("quantity_change")

        try:
            change_value = int(quantity_change) if quantity_change else 1
        except ValueError:
            change_value = 1

        # Xác định là tăng hay giảm
        if intent_name == "update_cart_decrease":
            change_value = -change_value  # Chuyển thành số âm nếu là giảm

        payload = None
        for item in items:
            product = db_service.products_collection.find_one({"_id": item["product"]})
            if product and product_name.lower() in product["name"].lower():
                item["quantity"] += int(change_value)
                payload = {
                    "user": user_id,
                    "items": items,
                }
                break

        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = requests.patch(
                f"http://localhost:8080/api/v1/carts/{cart['_id']}",
                json=payload,
                headers=headers,
                timeout=10,
            )

            if response.status_code in [200, 201]:
                dispatcher.utter_message(
                    text=f"Sản phẩm {product_name} đã được cập nhật thành công."
                )
            else:
                dispatcher.utter_message(
                    text="Xin lỗi, đã có lỗi xảy ra khi cập nhật số sản phẩm trong giỏ hàng."
                )
                print(f"Backend error: {response.status_code} - {response.text}")
        except Exception as e:
            dispatcher.utter_message(
                text="Đã có lỗi kết nối đến máy chủ. Vui lòng thử lại sau."
            )
            print(f"Error calling cart API: {e}")
        return [AllSlotsReset()]
