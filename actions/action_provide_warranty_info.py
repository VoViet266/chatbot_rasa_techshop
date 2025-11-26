from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from pymongo import MongoClient
from bson.objectid import ObjectId
import re
from rasa_sdk.events import (
    AllSlotsReset
)
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
        category_collections = db["categories"]

        category_name = tracker.get_slot("category")
        query = {}
        
        category_display_name = "tất cả sản phẩm"

        if category_name:
            # Tìm category ID dựa trên tên (case-insensitive)
            category_doc = category_collections.find_one({"name": {"$regex": f"^{category_name}$", "$options": "i"}})
            if category_doc:
                category_id = category_doc["_id"]
                # Tìm warranty có chứa category_id HOẶC không có field categories (áp dụng chung) HOẶC categories rỗng
                query = {
                    "$or": [
                        {"categories": category_id},
                        {"categories": {"$exists": False}},
                        {"categories": []},
                        {"categories": None}
                    ]
                }
                category_display_name = category_doc["name"]
            else:
                 # Nếu không tìm thấy category, có thể tìm theo text chung hoặc trả về mặc định
                 pass

        warranties_info = list(warranty_collections.find(query))

        if not warranties_info: 
            dispatcher.utter_message(text=f"Hiện tại chưa có chính sách bảo hành nào cho {category_display_name}.")
        else:
            message = f"<p>Chính sách bảo hành cho <strong>{category_display_name}</strong>:</p>"
            
            message += "<ul>"
            
            for w in warranties_info:
                name = w.get("name", "Chính sách không tên")
                description = w.get("description", "Không có mô tả chi tiết.")
                price = w.get("price", 0)
                duration = w.get("durationMonths", 0)
                
                if not price:
                    price_str = "Miễn phí"
                else:
                    price_str = f"{price:,.0f}đ"

                
                message += f"""<li>
                    <strong>{name}</strong> ({duration} tháng) - Giá: {price_str}<br/>
                    {description}
                </li>"""
            message += "</ul>"
            
            dispatcher.utter_message(text=message)

        return [AllSlotsReset()]