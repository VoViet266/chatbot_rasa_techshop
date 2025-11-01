from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from pymongo import MongoClient
from utils.render_product_ui import render_ui

class ActionProvideProductInfo(Action):
    def name(self):
        return "action_provide_product_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):

        product_name_slot = tracker.get_slot("product")

        if not product_name_slot:
            dispatcher.utter_message(text="Bạn muốn biết thông tin sản phẩm nào?")
            return []

        search_pipeline = [
            {
                "$search": {
                    "index": "tech_ai_search", 
                    "text": {
                        "query": product_name_slot,
                        "path": "name", 
                        "fuzzy": {
                            # Cho phép tối đa 2 lỗi chính tả
                            "maxEdits": 2, 
                            # Yêu cầu 2 chữ cái đầu phải đúng, tránh sai lệch quá
                            "prefixLength": 2 
                        }
                    }
                }
            },
             {
        "$lookup": {
            "from": "brands",
            "localField": "brand",
            "foreignField": "_id",
            "as": "brand_info"
        }
    },
    { "$unwind": { "path": "$brand_info", "preserveNullAndEmptyArrays": True } },
    {
        "$lookup": {
            "from": "categories",
            "localField": "category",
            "foreignField": "_id",
            "as": "category_info"
        }
    },
    { "$unwind": { "path": "$category_info", "preserveNullAndEmptyArrays": True } },
    {
        "$project": {
            "name": 1,
            "brand": "$brand_info.name",
            "category": "$category_info.name",
            "discount": 1
        }
    },
    { "$limit": 5 }
]
        
 
        client = MongoClient("mongodb+srv://VieDev:durNBv9YO1TvPvtJ@cluster0.h4trl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
        db = client["techshop_db"]
        products_collection = db["products"]
        variants_collection = db["variants"]
        brands_collection = db["brands"]

        # Tìm product theo $search (Atlas Search)
        # dùng .aggregate() thay vì .find()
        product_cursor = products_collection.aggregate(search_pipeline)
     
        try:
            product_from_db = next(product_cursor)
        except StopIteration:
            product_from_db = None # Không tìm thấy

        if not product_from_db:
            dispatcher.utter_message(text=f"Xin lỗi, tôi không tìm thấy thông tin cho sản phẩm {product_name_slot}.")
            return []

    
        variant_ids = product_from_db.get("variants", [])
        if not variant_ids:
            dispatcher.utter_message(text=f"Sản phẩm {product_from_db['name']} hiện chưa có thông tin.")
            return []

    
        variants = variants_collection.find({"_id": {"$in": variant_ids}})
        brand = brands_collection.find_one({"_id": product_from_db["brand"]})
        if brand:
            brand.pop("createdAt", None)
            brand.pop("updatedAt", None)
            brand.pop("deletedAt", None)

        variants = list(variants)
        for v in variants:
            v.pop("createdAt", None)
            v.pop("updatedAt", None)
            v.pop("deletedAt", None)

        product_from_db["brand"] = brand["name"] if brand else "N/A"
        product_from_db["variants"] = variants
        product_from_db.pop("createdAt", None)
        product_from_db.pop("updatedAt", None)
        product_from_db.pop("deletedAt", None)

        for variant in variants:
            product = products_collection.find_one({ "variants": variant['_id'] })
            if product:
                variant['discount'] = product.get('discount', 0)
                battery_capacity = product.get('attributes', {}).get('batteryCapacity')
                if battery_capacity:
                    variant['battery'] = battery_capacity
                variant['product_id'] = product.get('_id')

        if len(variants) == 0:
            dispatcher.utter_message(text=f"Sản phẩm {product_from_db['name']} hiện chưa có thông tin.")
        else:
            header = f"""<div>Hiện {product_from_db["name"]} có {len(variants)} biến thể</div>"""
            variant_html = render_ui(variants)
            final_result = header + variant_html
            dispatcher.utter_message(text=final_result, html=True)
            
        return []