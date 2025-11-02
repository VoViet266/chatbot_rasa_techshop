from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from utils.database import DatabaseService
from utils.render_product_ui import render_product_card #
from bson import ObjectId
import json

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

        # 1. Pipeline tìm kiếm sản phẩm (giữ nguyên)
        search_pipeline = [
            {
                "$search": {
                    "index": "tech_ai_search", 
                    "text": {
                        "query": product_name_slot,
                        "path": "name", 
                        "fuzzy": {"maxEdits": 2, "prefixLength": 2 }
                    }
                }
            },
            {"$lookup": {"from": "brands", "localField": "brand", "foreignField": "_id", "as": "brand_info"}},
            {"$unwind": { "path": "$brand_info", "preserveNullAndEmptyArrays": True } },
            {"$lookup": {"from": "categories", "localField": "category", "foreignField": "_id", "as": "category_info"}},
            {"$unwind": { "path": "$category_info", "preserveNullAndEmptyArrays": True } },
            {
                "$project": {
                    "name": 1,
                    "brand": "$brand_info.name",
                    "category": "$category_info.name",
                    "discount": 1,
                    "variants": 1,
                    "attributes": 1
                }
            },
            { "$limit": 1 }
        ]
        
        product_cursor = db.products_collection.aggregate(search_pipeline)
    
        try:
            product_from_db = next(product_cursor)
        except StopIteration:
            product_from_db = None

        if not product_from_db:
            dispatcher.utter_message(text=f"Xin lỗi, tôi không tìm thấy thông tin cho sản phẩm {product_name_slot}.")
            return []

        # 2. Lấy danh sách variants (giữ nguyên)
        variant_ids = product_from_db.get("variants", [])
        if not variant_ids:
            dispatcher.utter_message(text=f"Sản phẩm {product_from_db['name']} hiện chưa có thông tin biến thể.")
            return []

        object_id_variants = [ObjectId(v_id) for v_id in variant_ids]
        variants = list(db.variants_collection.find({"_id": {"$in": object_id_variants}}))
        
        if not variants:
            dispatcher.utter_message(text=f"Sản phẩm {product_from_db['name']} hiện chưa có thông tin biến thể.")
            return []


        product_html_card = render_product_card(product_from_db, variants)
        buttons = []
        text_variant_list = [] 
        for v in variants:
            button_title = v.get("name", "Chọn")
            
            # Thêm vào danh sách text
            text_variant_list.append(f"  •  {button_title}")

            # Tạo payload cho button
            payload_data = {
                "variant_id": str(v.get('_id')),
                "variant_name": v.get("name")
            }
            buttons.append({
                "title": button_title[:64], # Giới hạn độ dài title
                "payload": f"/select_variant{json.dumps(payload_data)}"
            })

        dispatcher.utter_message(text=product_html_card, html=True, buttons=buttons)
        return []

# --- ActionProvideProductPrice (Không thay đổi) ---
class ActionProvideProductPrice(Action):
    def name(self):
        return "action_provide_product_price"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):
        
        # ... (Giữ nguyên logic của bạn)
        db = DatabaseService()
        product_name_slot = tracker.get_slot("product")
        if not product_name_slot:
            dispatcher.utter_message(text="Bạn muốn hỏi giá sản phẩm nào ạ?")
            return []
        # ... (Phần còn lại giữ nguyên)

        # (Code gốc của bạn cho ActionProvideProductPrice)
        product_data = db.products_collection.find_one({"name": product_name_slot})

        if not product_data:
            dispatcher.utter_message(text=f"Xin lỗi, tôi không tìm thấy sản phẩm {product_name_slot}.")
            return []

        variants_id = product_data.get("variants", [])
        product_name = product_data.get("name", product_name_slot)
        discount = product_data.get("discount", 0)

        # Chuyển đổi ID sang ObjectId nếu cần
        try:
            object_id_variants = [ObjectId(v_id) for v_id in variants_id]
            variants = list(db.variants_collection.find({"_id": {"$in": object_id_variants}}))
        except:
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