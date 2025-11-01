from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from utils.database import DatabaseService
from utils.render_product_ui import render_ui

class ActionProvideProductInfo(Action):
    def name(self):
        return "action_provide_product_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):

        product_name_slot = tracker.get_slot("product")
        db = DatabaseService()
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
            "discount": 1,
            "variants": 1
        }
    },
    { "$limit": 5 }
]
        
        # Tìm product theo $search (Atlas Search)
        # dùng .aggregate() thay vì .find()
        product_cursor = db.products_collection.aggregate(search_pipeline)
     
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

    
        variants = db.variants_collection.find({"_id": {"$in": variant_ids}})
        brand = db.brands_collection.find_one({"_id": product_from_db["brand"]})
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
            product = db.products_collection.find_one({ "variants": variant['_id'] })
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

class ActionProvideProductPrice(Action):
    def name(self):
        return "action_provide_product_price"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):
        db = DatabaseService()
    
        product_name_slot = tracker.get_slot("product")
        if not product_name_slot:
            dispatcher.utter_message(text="Bạn muốn hỏi giá sản phẩm nào ạ?")
            return []

        product_data = db.products_collection.find_one({"name": product_name_slot})

        if not product_data:
            dispatcher.utter_message(text=f"Xin lỗi, tôi không tìm thấy sản phẩm {product_name_slot}.")
            return []

        variants_id = product_data.get("variants", [])
        product_name = product_data.get("name", product_name_slot)
        discount = product_data.get("discount", 0)

        variants = list(db.variants_collection.find({"_id": {"$in": variants_id}}))
        if not variants:
            dispatcher.utter_message(text=f"Sản phẩm {product_name} chưa có thông tin giá. Bạn vui lòng liên hệ sau ạ.")
            return []

        prices = [v.get('price') for v in variants if v.get('price') is not None and v.get('price') > 0]
        
        if not prices:
            dispatcher.utter_message(text=f"Sản phẩm {product_name} chưa có thông tin giá. Bạn vui lòng liên hệ sau ạ.")
            return []

        min_price = min(prices)
        max_price = max(prices)

        if discount > 0:
            min_price_final = min_price * (1 - discount / 100)
            max_price_final = max_price * (1 - discount / 100)
            
            if min_price == max_price:
                message = (f"Dạ, {product_name} đang có giá <strike>{min_price:,.0f} VNĐ</strike>, "
                           f"được giảm {discount}% chỉ còn <b>{min_price_final:,.0f} VNĐ</b> ạ.")
            else:
                message = (f"Dạ, {product_name} có nhiều phiên bản, giá gốc từ <strike>{min_price:,.0f}</strike> đến <strike>{max_price:,.0f} VNĐ</strike>. "
                           f"Hiện đang giảm {discount}%, nên giá chỉ còn từ <b>{min_price_final:,.0f}</b> đến <b>{max_price_final:,.0f} VNĐ</b> ạ.")
        else:
            if min_price == max_price:
                message = f"Dạ, {product_name} có giá <b>{min_price:,.0f} VNĐ</b> ạ."
            else:
                message = f"Dạ, {product_name} có nhiều phiên bản, giá dao động từ <b>{min_price:,.0f}</b> đến <b>{max_price:,.0f} VNĐ</b> ạ."
            
        dispatcher.utter_message(text=message)
        return []
