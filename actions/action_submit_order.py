from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, AllSlotsReset

class ActionSubmitOrder(Action):

    def name(self) -> Text:
        return "action_submit_order"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        user_id = tracker.sender_id


      
        # (1) Lấy tất cả dữ liệu từ các slot đã được điền trong form
        product = tracker.get_slot("product")
        variant = tracker.get_slot("variant")
        full_name = tracker.get_slot("full_name")
        phone_number = tracker.get_slot("phone_number")
        address = tracker.get_slot("address")
        quantity = tracker.get_slot("quantity")
        
        

        # (2) Hiển thị lại thông tin cho người dùng xác nhận (tùy chọn nhưng nên có)
        summary_message = (
            f"Xác nhận đơn hàng của bạn:\n"
            f"Sản phẩm: {product}\n"
            f"Phiên bản: {variant}\n"
            f"Số lượng: {quantity}\n"
            f"Họ và tên: {full_name}\n"
            f"Số điện thoại: {phone_number}\n"
            f"Địa chỉ: {address}\n"
           
        )
        print(summary_message)  # In ra console để kiểm tra 
        dispatcher.utter_message(text=summary_message)
        
        # (3) Chuẩn bị dữ liệu để gửi đi
        order_payload = {
            "product": product,
            "quantity": quantity,
            "variant": variant,
            "customer": {
                "full_name": full_name,
                "phone_number": phone_number,
                "address": address
            },
         
        }
        print("Dữ liệu đơn hàng đã chuẩn bị để gửi đi:", order_payload)
        # Gửi dữ liệu đơn hàng đến hệ thống xử lý (API, database, v.v.) - phần này cần được triển khai thêm tùy theo yêu cầu cụ thể
        #..........................................................
        dispatcher.utter_message(response="utter_order_summary")

        # (4) Xóa tất cả các slot để chuẩn bị cho đơn hàng tiếp theo
        return [AllSlotsReset()]