from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, AllSlotsReset
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
        dispatcher.utter_message(text=product_html_card, html=True)
        
        buttons = []
        text_variant_list = [] 
        for v in variants:
            button_title = v.get("name", "Chọn")
            text_variant_list.append(f"  •  {button_title}")

            # Tạo payload cho button
            payload_data = {
                "variant_id": str(v.get('_id')),
                "variant_name": v.get("name")
            }
            buttons.append({
                "title": button_title[:64],
                "payload": f"/show_variant_details {json.dumps(payload_data)}"})
        
        if buttons:
            dispatcher.utter_message(
                text="Bạn có thể chọn nhanh một phiên bản:",
                buttons=buttons[:10] 
            )
            
        return []
class ActionShowVariantDetails(Action):
    def name(self):
        return "action_show_variant_details"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):

        # 1. Lấy slot như cũ
        variant_id_str = tracker.get_slot("variant_id")
        variant_name = tracker.get_slot("variant_name")

        if not variant_id_str:
            dispatcher.utter_message(text="Có lỗi, tôi không nhận được thông tin phiên bản.")
            return []

        # 2. Lấy sender_id để biết là user nào
        # Chúng ta set nó vào slot để các action sau (như add_to_cart) có thể dùng
        user_id = tracker.sender_id
        
        # 3. Tạo payload data (chứa cả variant_id và user_id)
        # Chúng ta truyền thông tin này cho action tiếp theo
        payload_data = json.dumps({
            "variant_id": variant_id_str,
            "user_id": user_id 
        })

        # 4. Tạo các nút bấm cho action mới
        buttons = [
            {
                "title": "🛒 Thêm vào giỏ hàng",
                "payload": f"/action_add_to_cart{payload_data}" 
            },
            {
                "title": "💰 Đặt hàng ngay",
                # Payload này gọi action "action_start_order"
                "payload": f"/order{payload_data}" 
            }
        ]
        
        # 5. Gửi tin nhắn xác nhận VÀ các nút bấm mới
        dispatcher.utter_message(
            text=f"✅ Bạn đã chọn **{variant_name}**. Bạn muốn làm gì tiếp theo?",
            buttons=buttons
        )

        # 6. (Quan trọng) Lưu user_id vào slot
        return [SlotSet("user_id", user_id)]
    
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