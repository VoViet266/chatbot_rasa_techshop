# from typing import Any, Text, Dict, List
# from rasa_sdk import Action, Tracker
# from rasa_sdk.executor import CollectingDispatcher
# from utils.database import DatabaseService
# from datetime import datetime

# class ActionSubmitFeedback(Action):
#     def name(self) -> Text:
#         return "action_submit_feedback"

#     def run(self, dispatcher: CollectingDispatcher,
#             tracker: Tracker,
#             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
#         feedback_rating = tracker.get_slot("feedback_rating")
#         feedback_comment = tracker.get_slot("feedback_comment")
#         user_id = tracker.sender_id
        
#         # If slots are empty (e.g. direct intent without filling slots), we can just log a generic feedback
#         # But the rule structure suggests we might want to ask for rating first.
#         # For simplicity in this action, we just log what we have.
        
#         db = DatabaseService()
        
#         feedback_data = {
#             "user_id": user_id,
#             "rating": feedback_rating,
#             "comment": feedback_comment,
#             "created_at": datetime.now(),
#             "source": "chatbot"
#         }
        
#         try:
#             # Use a specific collection for chatbot feedback
#             db.db.chatbot_feedback.insert_one(feedback_data)
#             # We don't utter message here because the rule handles the thanks message
#         except Exception as e:
#             print(f"Error saving feedback: {e}")
            
#         return []
