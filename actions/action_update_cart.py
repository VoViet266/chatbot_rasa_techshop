import requests
from rasa_sdk import Action, Tracker
from bson import ObjectId
from utils.database import DatabaseService
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

class ActionUpdateCart(Action):
    def name(self) -> str:
        return "action_update_cart_quantity"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict) -> list:
        # Lấy thông tin từ slots
        product_name_slot = tracker.get_slot("product_name")
        quantity_action = tracker.get_slot("quantity_action")  # increase / decrease
        quantity_change = tracker.get_slot("quantity_change")
        user_id = tracker.sender_id
        
        metadata = tracker.latest_message.get("metadata", {})
        token = metadata.get("accessToken")

        # Validate user
        if not user_id or not ObjectId.is_valid(user_id):
            dispatcher.utter_message(text="Quý khách vui lòng đăng nhập để thực hiện thao tác này.")
            return [SlotSet("quantity_action", None), SlotSet("quantity_change", None)]

        # Validate product name
        if not product_name_slot:
            dispatcher.utter_message(text="Bạn muốn cập nhật số lượng cho sản phẩm nào?")
            return [SlotSet("quantity_action", None), SlotSet("quantity_change", None)]

        # Lấy giỏ hàng từ database
        db_service = DatabaseService()
        cart = db_service.carts_collection.find_one({"user": ObjectId(user_id)})

        if not cart or cart.get("isDeleted", False) or not cart.get("items"):
            dispatcher.utter_message(text="Giỏ hàng của bạn hiện đang trống.")
            return [SlotSet("quantity_action", None), SlotSet("quantity_change", None)]

        # Parse số lượng thay đổi
        try:
            change_value = int(quantity_change) if quantity_change else 1
        except ValueError:
            change_value = 1

        # Xử lý cập nhật giỏ hàng
        updated_items = []
        product_found = False
        response_message = ""

        for item in cart.get("items", []):
            # Lấy product ID và tìm trong DB
            raw_product_id = item.get("product")
            product_id = str(raw_product_id["_id"]) if isinstance(raw_product_id, dict) else str(raw_product_id)
            
            product_in_db = db_service.products_collection.find_one({"_id": ObjectId(product_id)})
            
            if not product_in_db:
                continue  # Bỏ qua item không hợp lệ

            # Chuẩn bị item payload với đầy đủ thông tin
            raw_variant_id = item.get("variant")
            raw_branch_id = item.get("branch")
            
            item_payload = {
                "product": product_id,
                "variant": str(raw_variant_id["_id"]) if isinstance(raw_variant_id, dict) else str(raw_variant_id),
                "color": item.get("color", ""),
                "quantity": item.get("quantity", 1),
                "price": item.get("price", 0),
                "branch": str(raw_branch_id["_id"]) if isinstance(raw_branch_id, dict) else str(raw_branch_id)
            }

            # Kiểm tra xem có phải sản phẩm cần cập nhật không
            if product_name_slot.lower() in product_in_db["name"].lower():
                product_found = True
                current_qty = item.get("quantity", 1)
                
                # Tính toán số lượng mới
                if quantity_action == "decrease":
                    new_qty = max(0, current_qty - change_value)
                    action_verb = "giảm"
                else:  # increase
                    new_qty = current_qty + change_value
                    action_verb = "tăng"
                
                # Xử lý theo số lượng mới
                if new_qty > 0:
                    item_payload["quantity"] = new_qty
                    updated_items.append(item_payload)
                    response_message = f"Đã {action_verb} {change_value} **{product_in_db['name']}** trong giỏ hàng. Số lượng hiện tại: {new_qty}."
                else:
                    # Không thêm item vào list = xóa khỏi giỏ hàng
                    response_message = f"Đã xóa **{product_in_db['name']}** khỏi giỏ hàng."
            else:
                # Giữ nguyên item không cần cập nhật
                updated_items.append(item_payload)

        # Kiểm tra có tìm thấy sản phẩm không
        if not product_found:
            dispatcher.utter_message(text=f"Không tìm thấy sản phẩm **{product_name_slot}** trong giỏ hàng của bạn.")
            return [SlotSet("quantity_action", None), SlotSet("quantity_change", None)]

        # Gọi API để cập nhật giỏ hàng
        payload = {
            "user": str(user_id),
            "items": updated_items
        }
        
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            api_url = f"http://localhost:8080/api/v1/carts/{cart['_id']}"
            response = requests.patch(
                api_url,
                json=payload,
                headers=headers,
                timeout=10
            )

            if response.status_code in [200, 201]:
                dispatcher.utter_message(text=f"✓ {response_message}")
            else:
                dispatcher.utter_message(text="⚠ Có lỗi xảy ra khi cập nhật giỏ hàng. Vui lòng thử lại.")
                print(f"Backend Error: {response.status_code} - {response.text}")

        except Exception as e:
            dispatcher.utter_message(text="⚠ Lỗi kết nối đến hệ thống. Vui lòng thử lại.")
            print(f"API Error: {e}")

        return [SlotSet("quantity_action", None), SlotSet("quantity_change", None)]