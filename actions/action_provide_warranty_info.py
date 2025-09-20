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

        if len(warranties_info) == 0:
            dispatcher.utter_message(text=f"Chưa có bất kỳ chính sách bảo hành nào.")
        else:
          message = f"""<p class="text-base">Hiện tại có các chính sách bảo hành như sau:</p>"""
          message += """<div class="flex flex-col gap-8">"""
          for w in warranties_info:
              message += f"""<div class="border border-gray-300 rounded-lg shadow-xs p-10">
              <span class="block"><strong>Tên:</strong> {w["name"]}</span>
              <p class="block text-justify line-clamp-3"><strong>Mô tả:</strong> {w["description"]}</p></div>"""
        message += """<span class="block">Nếu muốn biết thêm thông tin chi tiết, đừng ngại hỏi nhé!</span></div>"""
            
        dispatcher.utter_message(text=message)

        return []
