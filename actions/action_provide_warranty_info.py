from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from pymongo import MongoClient

class ActionProvideWarrantyInfo(Action):
    def name(self):
        return "action_provide_warranty_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):

        # Kết nối MongoDB
        client = MongoClient("mongodb+srv://VieDev:durNBv9YO1TvPvtJ@cluster0.h4trl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
        db = client["techshop_db"]
        warranty_collections = db["warrantypolicies"]
        warranties_info = list(warranty_collections.find())

        if not warranties_info: 
            dispatcher.utter_message(text="Chưa có bất kỳ chính sách bảo hành nào.")
        else:
            # B
            message = "<p>Hiện tại có các chính sách bảo hành như sau:</p>"
            
            message += "<ul>"
            
            
            for w in warranties_info:
                name = w.get("name", "Chính sách không tên")
                description = w.get("description", "Không có mô tả chi tiết.")
                
                message += f"""<li> - <strong>{name}:</strong> {description}.</li>"""
            message += "</ul>"
            message += "<p>Nếu muốn biết thêm thông tin chi tiết, đừng ngại hỏi nhé!</p>"
            
            dispatcher.utter_message(text=message)

        return []