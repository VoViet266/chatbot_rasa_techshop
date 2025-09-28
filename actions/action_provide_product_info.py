from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from pymongo import MongoClient
import json
from utils.convert_to_json import serialize_doc

class ActionProvideProductInfo(Action):
    def name(self):
        return "action_provide_product_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):

        product_name = tracker.get_slot("product")

        if not product_name:
            dispatcher.utter_message(text="Bạn vui lòng cho tôi biết tên sản phẩm nhé.")
            return []

        # Kết nối MongoDB
        client = MongoClient("mongodb+srv://VieDev:durNBv9YO1TvPvtJ@cluster0.h4trl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
        db = client["techshop_db"]
        products_collection = db["products"]
        variants_collection = db["variants"]
        brands_collection = db["brands"]

        # 1. Tìm product theo tên
        product = products_collection.find_one({"name": {"$regex": product_name, "$options": "i"}})

        if not product:
            dispatcher.utter_message(text=f"Xin lỗi, tôi không tìm thấy thông tin cho sản phẩm {product_name}.")
            return []

        # 2. Lấy danh sách variant IDs từ product
        variant_ids = product.get("variants", [])
        if not variant_ids:
            dispatcher.utter_message(text=f"Sản phẩm {product['name']} hiện chưa có thông tin.")
            return []

        # 3. Tìm variants theo _id
        variants = variants_collection.find({"_id": {"$in": variant_ids}})
        brand = brands_collection.find_one({"_id": product["brand"]})
        brand.pop("createdAt", None)
        brand.pop("updatedAt", None)
        brand.pop("deletedAt", None)

        variants = list(variants)
        for v in variants:
          v.pop("createdAt", None)
          v.pop("updatedAt", None)
          v.pop("deletedAt", None)

        product["brand"] = brand["name"] if brand else "N/A"
        product["variants"] = variants
        product.pop("createdAt", None)
        product.pop("updatedAt", None)
        product.pop("deletedAt", None)

        if len(variants) == 0:
            dispatcher.utter_message(text=f"Sản phẩm {product['name']} hiện chưa có thông tin.")
        else:
            product_serialized = serialize_doc(product)
            dispatcher.utter_message(json_message=product_serialized)
        return []
