
from rasa_sdk import Action, Tracker
from bson import ObjectId
from rasa_sdk.executor import CollectingDispatcher
from typing import Any, Text, Dict, List
from utils.database import DatabaseService
from rasa_sdk.events import SlotSet
import logging

logger = logging.getLogger(__name__)

class ActionGetInformation(Action):
    def name(self) -> Text:
        return "action_get_user_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        user_id = tracker.sender_id
        user_name = None
        events = []

        # Kiểm tra xem user_id có phải là ObjectId hợp lệ không
        if user_id and user_id != 'default' and ObjectId.is_valid(user_id):
            try:
                db_service = DatabaseService()
                user_infor = db_service.users_collection.find_one({"_id": ObjectId(user_id)})
                
                if user_infor:
                    user_name = user_infor.get("name")
                    # Lưu user_name vào slot để dùng cho các hội thoại sau
                    events.append(SlotSet("user_name", user_name))
            except Exception as e:
                logger.error(f"Lỗi khi lấy thông tin user: {e}")

        # Logic chào hỏi
        if user_name:
            # Chào theo tên
            dispatcher.utter_message(response="utter_greet_personalized", user_name=user_name)
        else:
            # Chào bình thường
            dispatcher.utter_message(response="utter_greet")
            
        return events