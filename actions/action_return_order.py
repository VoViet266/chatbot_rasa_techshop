
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import AllSlotsReset
import requests
import os
from dotenv import load_dotenv

load_dotenv()
from utils.database import DatabaseService
from bson import ObjectId

class ActionReturnOrder(Action):
    def name(self) -> Text:
        return "action_return_order"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        order_id = tracker.get_slot("order_id")
        return_reason = tracker.get_slot("return_reason")
        metadata = tracker.latest_message.get("metadata", {})
        token = metadata.get("accessToken")
        if not order_id:
            dispatcher.utter_message(text="Vui lòng cung cấp mã đơn hàng của bạn.")
            return []
        
        if not return_reason:
            dispatcher.utter_message(text="Vui lòng cho biết lý do trả hàng.")
            return []

        try:
            db = DatabaseService()      
            order = None
            try:
                # Thử tìm kiếm với ObjectId nếu là 24 ký tự hex
                if ObjectId.is_valid(order_id):
                    order = db.orders_collection.find_one({"_id": ObjectId(order_id)})
            except Exception as e:
                print(f"Error finding by ObjectId: {e}")
            
            if not order:
                order = db.orders_collection.find_one({"order_id": order_id})
            
            if not order:
                dispatcher.utter_message(
                    text=f"Không tìm thấy đơn hàng với mã: {order_id}. Vui lòng kiểm tra lại."
                )
                return [AllSlotsReset()]

            # Kiểm tra trạng thái đơn hàng: chỉ cho phép trả hàng khi đã giao (DELIVERED)
            status = (order.get("status") or "").upper()
            if status != "DELIVERED":
                dispatcher.utter_message(
                    text=(
                        f"Đơn hàng này chưa được giao nên không thể yêu cầu trả hàng. "
                        f"Trạng thái hiện tại: {status}. "
                        "Vui lòng liên hệ hỗ trợ nếu cần."
                    )
                )
                return [AllSlotsReset()]

            # Kiểm tra nếu đã trả
            if order.get("isReturned") or status == "RETURNED":
                dispatcher.utter_message(
                    text="Đơn hàng này đã được trả hoặc đang trong tiến trình trả hàng."
                )
                return [AllSlotsReset()]
            headers = {
                "Content-Type": "application/json",
            }
            if token:
                headers["Authorization"] = f"Bearer {token}"
                
            try:
                response = requests.patch(
                    f"{os.getenv('BACKEND_URL')}orders/request-return/{order_id}",
                    json={"returnReason": return_reason},
                    headers= headers,
                    timeout=10,
                )
                if response.status_code in (200, 201):
                    dispatcher.utter_message(
                        text=(
                            f"Yêu cầu trả hàng của bạn đã được ghi nhận. "
                            f"Mã đơn hàng: {order_id}. "
                            "Chúng tôi sẽ liên hệ với bạn để hướng dẫn tiếp theo."
                        )
                    )
                else:
                    dispatcher.utter_message(
                        text="Có lỗi xảy ra khi xử lý yêu cầu trả hàng. Vui lòng thử lại sau."
                    )
                    print(f"Return request error: {response.status_code}, {response.text}")
            except requests.exceptions.RequestException as e:
                print(f"Error requesting return: {str(e)}")
                dispatcher.utter_message(
                    text="Không thể kết nối với hệ thống. Vui lòng thử lại sau."
                )

        except Exception as e:
            print(f"Error in action_return_order: {str(e)}")
            dispatcher.utter_message(text="Có lỗi xảy ra, vui lòng thử lại.")

        # Reset slots sau khi hoàn tất
        return [AllSlotsReset()]