
from rasa_sdk import Action, Tracker
from bson import ObjectId
from rasa_sdk.executor import CollectingDispatcher
from typing import Any, Text, Dict, List
from utils.database import DatabaseService
from rasa_sdk.events import SlotSet

class ActionGetInformation(Action):
    def name(self) -> Text:
        return "action_get_user_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        user_id = tracker.sender_id
        db_service = DatabaseService()
        if user_id != 'default':
            user_infor=db_service.users_collection.find_one({"_id": ObjectId(user_id)})
            user_name= user_infor.get("name")
            return [SlotSet("user_name", user_name)]
        else: 
            dispatcher.utter_message(response="utter_greet")
        return []