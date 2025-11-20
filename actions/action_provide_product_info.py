from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from utils.database import DatabaseService
from utils.render_product_ui import render_product_card 
from utils.product_pipelines import build_search_pipeline
from bson import ObjectId
import json

class ActionProvideProductInfo(Action):
    def name(self):
        return "action_provide_product_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):

        product_name_slot = tracker.get_slot("product_name")
        db = DatabaseService()
        if not product_name_slot:
            dispatcher.utter_message(text="Bạn muốn biết thông tin sản phẩm nào?")
            return []

        pipeline =  build_search_pipeline(product_name_slot)
        product_cursor = db.products_collection.aggregate(pipeline)
    
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

        variant_id_str = tracker.get_slot("variant_id")
        variant_name = tracker.get_slot("variant_name")

        if not variant_id_str:
            dispatcher.utter_message(text="!!Có lỗi: Không nhận được mã sản phẩm.")
            return []

        # 2. Kết nối DB và Tìm kiếm
        db = DatabaseService() # Đảm bảo class này đã được khởi tạo đúng
        variant_data = None
        
        try:
            # Thử tìm bằng ObjectId trước
            variant_data = db.variants_collection.find_one({"_id": ObjectId(variant_id_str)})
        except Exception:
            # Nếu lỗi format ObjectId thì tìm bằng string
            variant_data = db.variants_collection.find_one({"_id": variant_id_str})

        if not variant_data:
            dispatcher.utter_message(text="Xin lỗi, tôi không tìm thấy thông tin trong kho dữ liệu.")
            return []

        price_raw = variant_data.get("price", 0)
        price_fmt = "{:,.0f}".format(price_raw).replace(",", ".") # VD: 10.000.000

        memory_data = variant_data.get("memory", {})
        ram = memory_data.get("ram", "N/A")
        storage = memory_data.get("storage", "N/A")
        colors_list = variant_data.get("color", [])
        
        # Mặc định
        color_display = "Tiêu chuẩn"
        image_url = "" 

        if colors_list and isinstance(colors_list, list) and len(colors_list) > 0:
            # Lấy danh sách tên các màu có sẵn: "Xanh, Đỏ, Tím"
            color_names = [c.get("colorName", "") for c in colors_list]
            color_display = ", ".join(filter(None, color_names))

            # Lấy ảnh đại diện: Lấy ảnh đầu tiên của màu đầu tiên trong danh sách
            first_color_option = colors_list[0]
            images = first_color_option.get("images", [])
            if images and len(images) > 0:
                image_url = images[0]
            else:
                
                image_url = "https://via.placeholder.com/300x200?text=No+Image"


        is_active = variant_data.get("isActive", True)
        status = "✅ Còn hàng" if is_active else "❌ Tạm ngưng kinh doanh"
        
        html_message = f"""
        <div style="background-color: #f9f9f9; padding: 15px; border-radius: 10px; border: 1px solid #ddd;">
            <div style="text-align: center; margin-bottom: 10px;">
                <img src="{image_url}" alt="{variant_name}" style="max-width: 100%; height: auto; border-radius: 8px; max-height: 250px; object-fit: cover;">
            </div>
            <h3 style="margin: 5px 0; color: #333;">{variant_name}</h3>
            <hr style="border: 0; border-top: 1px solid #ccc;">
            <p style="margin: 5px 0;"><b> Giá bán:</b> <span style="color: #d9534f; font-size: 1.1em; font-weight: bold;">{price_fmt} VNĐ</span></p>
            <p style="margin: 5px 0;"><b> Cấu hình:</b> RAM {ram} | ROM {storage}</p>
            <p style="margin: 5px 0;"><b> Màu sắc:</b> {color_display}</p>
            <p style="margin: 5px 0;"><b> Tình trạng:</b> {status}</p>
        </div>
        """

        # 5. TẠO NÚT BẤM (BUTTONS)
        user_id = tracker.sender_id
        payload_dict = {
            "variant_id": str(variant_data.get("_id")), # Convert ObjectId to string
            "user_id": user_id,
        }
        payload_json = json.dumps(payload_dict)

        buttons = [
            {
                "title": "🛒 Thêm vào giỏ hàng",
                "payload": f"/add_to_cart{payload_json}" 
            },
            {
                "title": "💳 Đặt hàng ngay",
                "payload": f"/order{payload_json}" 
            }
        ]
        
        
        dispatcher.utter_message(text=html_message, buttons=buttons)
        return [SlotSet("user_id", user_id)]

class ActionShowListVariants(Action):
    def name(self) :
        return "action_show_list_variants"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker,
            domain: dict):
            
        product_name_slot = tracker.get_slot("product_name")
        
        if not product_name_slot:
            dispatcher.utter_message(text="Bạn muốn biết thông tin sản phẩm nào?")
            return []

        db = DatabaseService()
        
        # 1. Tìm sản phẩm cha
        pipeline = build_search_pipeline(product_name_slot)
        product_cursor = db.products_collection.aggregate(pipeline)
        
        try:
            product_from_db = next(product_cursor)
        except StopIteration:
            product_from_db = None

        if not product_from_db:
            dispatcher.utter_message(text=f"Xin lỗi, tôi không tìm thấy sản phẩm {product_name_slot}.")
            return []

        # 2. Lấy danh sách ID biến thể
        variant_ids = product_from_db.get("variants", [])
        if not variant_ids:
            dispatcher.utter_message(text=f"Sản phẩm {product_from_db['name']} hiện chưa có thông tin biến thể.")
            return []

        # 3. Query chi tiết các biến thể
        object_id_variants = [ObjectId(v_id) for v_id in variant_ids]
        variants = list(db.variants_collection.find({"_id": {"$in": object_id_variants}}))

        if not variants:
            dispatcher.utter_message(text=f"Sản phẩm {product_from_db['name']} hiện chưa có thông tin biến thể.")
            return []      
        list_items_html = ""
        buttons = []

        for v in variants:
            # Lấy thông tin cơ bản
            v_name = v.get("name", "N/A")
            price_raw = v.get("price", 0)
            price_fmt = "{:,.0f}".format(price_raw).replace(",", ".")
            
            # Lấy thêm thông tin RAM/ROM cho rõ ràng (dựa trên schema cũ bạn đưa)
            memory = v.get("memory", {})
            ram = memory.get("ram", "")
            storage = memory.get("storage", "")
            spec_str = f"({ram}/{storage})" if ram and storage else ""

            # Tạo dòng HTML: • Tên (Ram/Rom): Giá đỏ
            # style="margin-bottom: 5px;" để các dòng thoáng hơn
            list_items_html += (
                f'<li style="margin-bottom: 8px;">'
                f'<b>{v_name}</b> <span style="font-size: 0.9em; color: #666;">{spec_str}</span>: '
                f'<span style="color: #d9534f; font-weight: bold;">{price_fmt} VNĐ</span>'
                f'</li>'
            )

            # Tạo button để user bấm chọn luôn (UX tốt hơn)
            payload_data = json.dumps({
                "variant_id": str(v.get("_id")),
                "variant_name": v_name
            })
            buttons.append({
                "title": f"Chọn {v_name}",
                "payload": f"/show_variant_details{payload_data}"
            })

        # 5. Đóng gói vào thẻ <ul> và gửi tin nhắn
        # style="list-style-type: disc;" đảm bảo luôn hiện chấm tròn
        full_html_message = (
            f"Dạ, sản phẩm <b>{product_from_db['name']}</b> có các phiên bản sau:<br><br>"
            f'<ul style="list-style-type: disc; padding-left: 20px; margin-top: 0;">'
            f"{list_items_html}"
            f"</ul>"
        )

        # Gửi tin nhắn HTML kèm Buttons
        dispatcher.utter_message(text=full_html_message)
        if buttons:
            dispatcher.utter_message(
                text="Bạn có thể chọn một phiên bản dưới đây:",
                buttons=buttons[:10] 
            )
            
        
        return []
    
class ActionProvideProductPrice(Action):
    def name(self):
        return "action_provide_product_price"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):
        
        db = DatabaseService()
        product_name_slot = tracker.get_slot("product_name")
        if not product_name_slot:
            dispatcher.utter_message(text="Bạn muốn hỏi giá sản phẩm nào ạ?")
            return []
        
        pipeline_search = build_search_pipeline(product_name_slot)
        product_data = list(db.products_collection.aggregate(pipeline_search))
        
        if not product_data:
            dispatcher.utter_message(text=f"Xin lỗi, tôi không tìm thấy sản phẩm {product_name_slot}.")
            return []
        product_data = product_data[0]
        variants_id = product_data.get("variants", [])
        product_name = product_data.get("name", product_name_slot)
        discount = product_data.get("discount", 0) 
        
        try:
            object_id_variants = [ObjectId(v_id) for v_id in variants_id]
            variants = list(db.variants_collection.find({"_id": {"$in": object_id_variants}}))
        except Exception:
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
    
    