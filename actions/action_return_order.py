import re
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import requests
from utils.database import DatabaseService
from bson import ObjectId


class ActionProcessReturnRequest(Action):
    def name(self) -> Text:
        return "action_process_return_request"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        order_id = next(tracker.get_latest_entity_values("order_id"), None)
        metadata = tracker.latest_message.get("metadata", {})
        token = metadata.get("accessToken")
        
        if not order_id:
            text = tracker.latest_message.get("text", "")
            match = re.search(r"[0-9a-fA-F]{24}", text)
            if match:
                order_id = match.group(0)
                
        if not order_id:
            dispatcher.utter_message(text="Vui lòng cung cấp mã đơn hàng của bạn.")
            return []

        # Lấy lý do trả hàng từ form / message
        return_reason = tracker.get_slot("provide_return_reason")
        if not return_reason:
            dispatcher.utter_message(text="Vui lòng cho biết lý do bạn muốn trả hàng.")
            return []
    
        db = DatabaseService()
        # Trong DB có thể lưu order._id hoặc order_id khác nhau; cố gắng tìm kiếm bằng cả hai
        order = db.orders_collection.find_one({"_id": ObjectId(order_id)})
    

        if not order:
            dispatcher.utter_message(text="Không tìm thấy đơn hàng với mã này. Vui lòng kiểm tra lại.")
            return []

        # Kiểm tra trạng thái đơn hàng: chỉ cho phép trả hàng khi đã giao (DELIVERED)
        status = (order.get("status") or "").upper()
        if status != "DELIVERED":
            dispatcher.utter_message(
                text=(
                    "Hiện tại đơn hàng của bạn chưa được giao nên không thể yêu cầu trả hàng. "
                    "Nếu bạn muốn hủy hoặc có thắc mắc khác, vui lòng cung cấp mã đơn hoặc mô tả thêm."
                )
            )
            return []

        # Trường hợp đã trả/đã yêu cầu trả
        if status == "RETURNED" or order.get("isReturned"):
            dispatcher.utter_message(text="Đơn hàng này đã được trả hoặc đang trong tiến trình trả hàng.")
            return []
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            # Gọi API backend để đăng ký yêu cầu trả hàng
            response = requests.patch(
                f"http://localhost:8080/api/v1/orders/request-return/{order_id}",
                json={"returnReason": return_reason},
                headers=headers,
                timeout=10,
            )

            if response.status_code in (200, 201):
                dispatcher.utter_message(
                    text=(
                        "Yêu cầu trả hàng của bạn đã được ghi nhận. "
                        f"Mã đơn hàng: {order_id}. Chúng tôi sẽ liên hệ với bạn để hướng dẫn tiếp theo."
                    )
                )
            else:
                dispatcher.utter_message(
                    text=(
                        "Có lỗi xảy ra khi xử lý yêu cầu trả hàng. Vui lòng thử lại sau hoặc liên hệ bộ phận hỗ trợ."
                    )
                )
                # optional: log backend response for debugging
                print("Return request error:", response.status_code, response.text)
        except Exception as e:
            print("Error requesting return:", str(e))
            dispatcher.utter_message(text="Không thể kết nối với hệ thống. Vui lòng thử lại sau.")

        return []