import requests
from bson import ObjectId
from rasa_sdk import Action, Tracker
from utils.database import DatabaseService
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import AllSlotsReset
from utils.validate_user import validate_user


class ActionDeleteFromCart(Action):
    def name(self) -> str:
        return "action_delete_from_cart"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        # Lấy user_id
        user_id = validate_user(
            tracker,
            dispatcher,
            message="Vui lòng đăng nhập để xóa sản phẩm khỏi giỏ hàng!",
        )
        product_name = tracker.get_slot("product_name")
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
            dispatcher.utter_message(text="Bạn vui lòng cho biết tên sản phẩm cần xóa!")
            return []
        
        print('Product name:', product_name)

        items = cart.get("items", [])
        if not items:
            dispatcher.utter_message(text="Giỏ hàng của bạn hiện đang trống.")
            return []

        payload = None
        product_to_delete = None

        for item in items:
            product = db_service.products_collection.find_one({"_id": ObjectId(item["product"])})
            if product and product_name.lower() in product["name"].lower():
                payload = {
                    "productId": str(item["product"]),
                    "variantId": str(item["variant"]),
                }
                product_to_delete = product
                break

        print('Payload:', payload)

        if not payload:
            dispatcher.utter_message(
                text=f"Sản phẩm '{product_name}' không tồn tại trong giỏ hàng của bạn."
            )
            return [AllSlotsReset()]

        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = requests.delete(
                "http://localhost:8080/api/v1/carts/remove-item",
                json=payload,
                headers=headers,
                timeout=10,
            )

            if response.status_code in [200, 201]:
                dispatcher.utter_message(
                    text=f"Sản phẩm {product_to_delete['name']} đã được xóa khỏi giỏ hàng thành công."
                )
            else:
                dispatcher.utter_message(
                    text="Xin lỗi, đã có lỗi xảy ra khi xóa sản phẩm khỏi giỏ hàng."
                )
                print(f"Backend error: {response.status_code} - {response.text}")
        except Exception as e:
            dispatcher.utter_message(
                text="Đã có lỗi kết nối đến máy chủ. Vui lòng thử lại sau."
            )
            print(f"Error calling cart API: {e}")
        return [AllSlotsReset()]
