from rasa_sdk import  Tracker
from rasa_sdk.executor import CollectingDispatcher

def _validate_user(tracker: Tracker, dispatcher: CollectingDispatcher, message: str = "Vui lòng đăng nhập để tiếp tục!!!") -> str:
    """Validate user_id từ tracker"""
    user_id = tracker.sender_id
    if not user_id:
        dispatcher.utter_message(text=message)
        return None
    return user_id