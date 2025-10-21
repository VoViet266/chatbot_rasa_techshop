# trong file actions.py
import pymongo
from rasa_sdk import Action, Tracker
from bson import ObjectId
from rasa_sdk.executor import CollectingDispatcher
from typing import Any, Text, Dict, List
import re

class ActionCheckStock(Action):
    def name(self) -> Text:
        return "action_check_stock"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # Lấy thông tin từ các slots
        product_name = tracker.get_slot("product")
        variant_name = tracker.get_slot("variant_name")

        if not product_name:
            dispatcher.utter_message(text="Bạn muốn kiểm tra tồn kho cho sản phẩm nào ạ?")
            return []
       
        client = pymongo.MongoClient("mongodb+srv://VieDev:durNBv9YO1TvPvtJ@cluster0.h4trl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
        db = client["techshop_db"]
        products_collection = db["products"]
        inventory_collection = db["inventories"] 

        product_doc = products_collection.find_one({"name": {"$regex": product_name, "$options": "i"}})

        if not product_doc:
            dispatcher.utter_message(text=f"Xin lỗi, tôi không tìm thấy sản phẩm nào có tên là '{product_name}'.")
            client.close()
            return []

        product_id = product_doc["_id"]
        inventory_doc = inventory_collection.find_one({"product": product_id})

        if not inventory_doc or not inventory_doc.get("variants"):
            dispatcher.utter_message(text=f"Rất tiếc, sản phẩm '{product_name}' hiện đã hết hàng hoặc chưa được nhập kho.")
            client.close()
            return []

        if variant_name:
            variant_found = False
            for variant in inventory_doc["variants"]:
                if variant_name.lower() in variant.get("variantColor", "").lower():
                    variant_found = True
                    stock_quantity = variant.get("stock", 0)
                    if stock_quantity > 0:
                        dispatcher.utter_message(text=f"Tin vui! ✅ Sản phẩm '{product_name}' phiên bản '{variant['variantColor']}' vẫn còn {stock_quantity} sản phẩm trong kho ạ.")
                    else:
                        dispatcher.utter_message(text=f"Rất tiếc! ❌ Sản phẩm '{product_name}' phiên bản '{variant['variantColor']}' đã tạm hết hàng.")
                    break 
            
            if not variant_found:
                dispatcher.utter_message(text=f"Xin lỗi, tôi không tìm thấy phiên bản '{variant_name}' cho sản phẩm '{product_name}'.")

    
        else:
            total_stock = 0
            available_variants = []
            for variant in inventory_doc["variants"]:
                stock_quantity = variant.get("stock", 0)
                if stock_quantity > 0:
                    total_stock += stock_quantity
                    available_variants.append(f"- {variant.get('variantColor', 'N/A')} (còn {stock_quantity} sản phẩm)")
            
            if total_stock > 0:
                variants_text = "\n".join(available_variants)
                message = (f"Dạ, sản phẩm '{product_name}' vẫn còn hàng ạ. "
                           f"Tổng cộng còn {total_stock} sản phẩm với các phiên bản sau:\n{variants_text}")
                dispatcher.utter_message(text=message)
            else:
                dispatcher.utter_message(text=f"Rất tiếc! ❌ Sản phẩm '{product_name}' hiện đã tạm hết hàng ở tất cả các phiên bản.")
        
        client.close()
        return []