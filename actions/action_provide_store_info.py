from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from pymongo import MongoClient

class ActionProvideStoreInfo(Action):
    def name(self):
        return "action_provide_store_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):

        # Kết nối MongoDB
        client = MongoClient("mongodb+srv://VieDev:durNBv9YO1TvPvtJ@cluster0.h4trl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
        db = client["techshop_db"]
        branches_collections = db["branches"]
        branches_info = list(branches_collections.find())

        if len(branches_info) == 0:
            dispatcher.utter_message(text=f"Xin lỗi! Hiện chưa có bất kỳ chi nhánh nào.")
        else:
          message = f"""<p class="text-base">Hiện tại, hệ thống có các chi nhánh như sau:</p>"""
          message += """<div class="flex flex-col gap-8">"""
          for br in branches_info:
              message += f"""<div class="border border-gray-300 rounded-lg shadow-xs p-10">
              <span class="block"><strong>Tên:</strong> {br["name"]}</span>
              <span class="block"><strong>Số điện thoại:</strong> {br["phone"]}</span>
              <span class="block"><strong>Email:</strong> {br["email"]}</span>
              <span class="block text-justify line-clamp-3"><strong>Địa chỉ:</strong> {br["address"]}</span>
              </div>"""
        message += """<span class="block">Nếu muốn biết thêm thông tin chi tiết, đừng ngại hỏi nhé!</span></div>"""
            
        dispatcher.utter_message(text=message)

        return []
