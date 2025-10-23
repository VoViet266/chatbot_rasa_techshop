# actions/actions.py

from importlib.metadata import metadata
from typing import Any, Text, Dict, List, Tuple, Optional
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, AllSlotsReset
from utils.database import DatabaseService
from bson import ObjectId
import regex
import requests
import json
from utils.format_currentcy import format_vnd


# Logic chung để lấy và xác thực thông tin đơn hàng từ DB
def _get_validated_order_info(tracker: Tracker, db_service: DatabaseService) -> Tuple[Optional[str], Optional[Dict]]:
  
    user_id = tracker.sender_id
   
    product_name = tracker.get_slot("product")
    variant_name = tracker.get_slot("variant_name")
    quantity_str = tracker.get_slot("quantity")

    # 1. Xác thực người dùng
    
    if not user_id or not ObjectId.is_valid(user_id):
        return "Để mua hàng, vui lòng đăng nhập.", None
    
    # Chỉ truy vấn khi user_id đã hợp lệ
    user_info = db_service.users_collection.find_one({"_id": ObjectId(user_id)})
    
    # Kiểm tra xem có tìm thấy người dùng trong DB không
    if not user_info:
        return "Không tìm thấy thông tin người dùng. Vui lòng thử đăng nhập lại.", None
    phone_number = user_info.get("phone", "")
    if not regex.match(r'^(0|\+84)(3[2-9]|5[6|8|9]|7[0|6-9]|8[1-5]|9[0-4|6-9])[0-9]{7}$', phone_number):
        return "Số điện thoại của bạn không hợp lệ. Vui lòng cập nhật lại thông tin cá nhân.", None
    # 2. Xác thực sản phẩm
    product_data = db_service.products_collection.find_one({"name": {"$regex": product_name, "$options": "i"}})
    if not product_data:
        return f"Xin lỗi, tôi không tìm thấy sản phẩm '{product_name}'. Vui lòng kiểm tra lại.", None

    # 3. Xác thực phiên bản (variant)
    variant_ids = product_data.get("variants", [])
    variants_cursor = db_service.variants_collection.find({"_id": {"$in": variant_ids}})
    
    found_variant = None
    for v in variants_cursor:
        if variant_name.lower() in v["name"].lower():
            found_variant = v
            break
            
    if not found_variant:
        return f"Xin lỗi, tôi không tìm thấy phiên bản '{variant_name}' cho sản phẩm {product_name}.", None

    # 4. Xác thực số lượng
    try:
        quantity = int(float(quantity_str))
        if quantity <= 0:
            quantity = 1
    except (ValueError, TypeError):
        quantity = 1
    
    # 5. Lấy địa chỉ mặc định
    addresses = user_info.get("addresses", [])
    default_address_obj = next((addr for addr in addresses if addr.get("default")), None)
    if default_address_obj:
        address_str = f'{default_address_obj["specificAddress"]}, {default_address_obj["addressDetail"]}'
    else:
        address_str = "Chưa có địa chỉ mặc định."

    # 6. Tính toán và trả về dữ liệu
    total_price = found_variant.get("price", 0) * quantity
    
    validated_data = {
        "user_id": user_id,
        "full_name": user_info.get("name", "N/A"),
        "phone_number": phone_number,
        "address": address_str,
        "product_name": product_data["name"],
        "product_id": str(product_data["_id"]),
        "variant_name": found_variant["name"],
        "variant_id": str(found_variant["_id"]),
        "variant_price": found_variant.get("price", 0),
        "quantity": quantity,
        "total_price": total_price
    }
    print(validated_data)
    return None, validated_data



class ActionReviewOrder(Action):
    def name(self) -> Text:
        return "action_preview_order"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        db_service = DatabaseService()
        error_message, order_data = _get_validated_order_info(tracker, db_service)

        # Nếu có lỗi trong quá trình xác thực, thông báo và reset
        if error_message:
            dispatcher.utter_message(text=error_message)
            return [AllSlotsReset()]

        # Nếu không có lỗi, hiển thị thông tin và lưu vào slot để action_submit_order sử dụng
        summary_message = (
            f"**Vui lòng xác nhận lại thông tin đơn hàng của bạn:\n"
            f"- Sản phẩm: **{order_data['product_name']}**\n"
            f"- Phiên bản: **{order_data['variant_name']}**\n"
            f"- Số lượng: **{order_data['quantity']}**\n"
            f"- Tổng cộng: **{format_vnd(order_data['total_price'])}**\n"
            f"**Thông tin giao hàng:**\n"
            f"- Người nhận: {order_data['full_name']}\n"
            f"- Số điện thoại: {order_data['phone_number']}\n"
            f"- Địa chỉ: {order_data['address']}\n\n"
            f"Bạn có muốn xác nhận đặt hàng không?"
        )
        dispatcher.utter_message(text=summary_message)
       
        # Lưu các thông tin quan trọng đã được xác thực vào slot
        return [
            SlotSet("validated_product_id", order_data["product_id"]),
            SlotSet("validated_variant_id", order_data["variant_id"]),
            SlotSet("validated_quantity", order_data["quantity"]),
            SlotSet("validated_price", order_data["variant_price"]),
            SlotSet("validated_total_price", order_data["total_price"]),
            SlotSet("validated_address", order_data["address"]),
            SlotSet("validated_customer_name", order_data["full_name"]),
            SlotSet("validated_phone", order_data["phone_number"])
        ]

class ActionSubmitOrder(Action):
    def name(self) -> Text:
        return "action_submit_order"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Lấy toàn bộ thông tin đã được xác thực từ slots
        user_id = tracker.sender_id
        metadata = tracker.latest_message.get("metadata", {})
        token = metadata.get("accessToken")

        product_id = tracker.get_slot("validated_product_id")
        variant_id = tracker.get_slot("validated_variant_id")
        price = tracker.get_slot("validated_price")
        quantity = tracker.get_slot("validated_quantity")
        total_price = tracker.get_slot("validated_total_price")
        address = tracker.get_slot("validated_address")
        customer_name = tracker.get_slot("validated_customer_name")
        phone = tracker.get_slot("validated_phone")

        # Kiểm tra xem các slot cần thiết có tồn tại không
        if not all([product_id, variant_id, quantity, total_price]):
            dispatcher.utter_message(text="Đã có lỗi xảy ra. Thông tin đơn hàng không đầy đủ. Vui lòng thử lại từ đầu.")
            return [AllSlotsReset()]

        order_payload = {
            "user": user_id,
            "recipient": {
                "name": customer_name,
                "phone": phone,
                "address": address,
                # "note": "" # Có thể thêm nếu cần
            },
            "buyer": { 
                "name": customer_name,
                "phone": phone,
            },
            "items": [{
                "product": product_id,
                "variant": variant_id,
                "quantity": quantity,
                "price": price,
                
            }],
            "totalPrice": total_price,
            "shippingAddress": address,
            "phone": phone,
            "customerName": customer_name,
            "status": "pending"
        }
        
            
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            
        try:
            response = requests.post("http://localhost:8080/api/v1/orders", json=order_payload, headers=headers, timeout=10)
            if response.status_code in [200, 201]:
                order_id = response.json().get("data", {}).get("_id", "N/A")
                dispatcher.utter_message(text=f" Đặt hàng thành công! Mã đơn hàng của bạn là #{order_id}.")
            else:
                dispatcher.utter_message(text="Xin lỗi, đã có lỗi xảy ra khi gửi đơn hàng đến hệ thống.")
                print(f"Backend error: {response.status_code} - {response.text}")
        except Exception as e:
            dispatcher.utter_message(text="Đã có lỗi kết nối đến máy chủ. Vui lòng thử lại sau.")
            print(f"Error submitting order: {str(e)}")
            
        return [AllSlotsReset()]

class ActionCancelOrder(Action):
    def name(self) -> Text:
        return "action_cancel_order"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text="Đơn hàng của bạn đã được hủy. Nếu bạn cần hỗ trợ thêm, đừng ngần ngại cho tôi biết nhé.")
        return [AllSlotsReset()]