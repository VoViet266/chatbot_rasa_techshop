import requests
from pymongo import MongoClient
from rasa_sdk.events import SlotSet, AllSlotsReset
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from typing import Any, Text, Dict, List, Tuple, Optional
from bson import ObjectId
from utils.product_pipelines import build_search_pipeline


from utils.database import DatabaseService
from utils.format_currentcy import format_vnd

class ActionAddToCart(Action):
    def name(self) -> str:
        return "action_add_to_cart"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        
        db_service = DatabaseService()
        
        # Lấy slot
        user_id = tracker.sender_id
        product_name = tracker.get_slot("product")
        variant_name = tracker.get_slot("variant_name") 
        variant_color = tracker.get_slot("variant_color")
        quantity_str = tracker.get_slot("quantity")
        branch_id = tracker.get_slot("selected_branch_id") 
        
        metadata = tracker.latest_message.get("metadata", {})
        token = metadata.get("accessToken")

        # 1. Kiểm tra đăng nhập
        if not user_id or not ObjectId.is_valid(user_id):
            dispatcher.utter_message(text="Quý khách vui lòng đăng nhập để sử dụng dịch vụ.")
            return []

        # 2. KỊCH BẢN 1: Chưa có SẢN PHẨM
        if not product_name:
            dispatcher.utter_message(text="Bạn muốn thêm sản phẩm nào vào giỏ hàng?")
            return []

        # Tìm sản phẩm
        pipeline_search = build_search_pipeline(product_name)
        product_data = list(db_service.products_collection.aggregate(pipeline_search))
        if not product_data:
            dispatcher.utter_message(text=f"Sản phẩm '{product_name}' không tồn tại. Vui lòng chọn sản phẩm khác.")
            return [AllSlotsReset()]
        product_data = product_data[0]
        variant_ids = product_data.get("variants", [])
        if not variant_ids:
            dispatcher.utter_message(text=f"Sản phẩm {product_name} hiện không có phiên bản nào.")
            return [AllSlotsReset()]

        # 3. KỊCH BẢN 2: Chưa có PHIÊN BẢN 
        if not variant_name:
            available_groups = db_service.variants_collection.distinct(
                "name", 
                {"_id": {"$in": variant_ids}}
            )

            buttons = []
            for variant_name in available_groups:
                buttons.append({
                    "title": f"{variant_name}",
                    "payload": f'/inform{{"variant_name": "{variant_name}"}}' 
                })
            
            dispatcher.utter_message(
                text=f"Bạn muốn thêm phiên bản nào của <b>{product_name}</b> vào giỏ?",
                buttons=buttons
            )
            # Giữ lại product_name và chờ người dùng chọn
            return [SlotSet("product", product_name)]

        # 4. KỊCH BẢN 3: Chưa có MÀU SẮC (variant_color)
        if not variant_color:
            try:
                available_colors_docs = db_service.variants_collection.find(
                    {"_id": {"$in": variant_ids}, "name": variant_name},
                    {"color": 1, "_id": 0}
                )
                
                available_colors = set()
                for doc in available_colors_docs:
                    for color_obj in doc.get("color", []):
                        if color_obj.get("colorName"):
                            available_colors.add(color_obj["colorName"])
                
            except Exception as e:
                print(f"Error querying distinct colors: {e}")
                dispatcher.utter_message(text="Đã có lỗi khi tải các màu của phiên bản.")
                return [AllSlotsReset()]
            
            if not available_colors:
                dispatcher.utter_message(text=f"Phiên bản {variant_name} không tìm thấy màu nào.")
                return [AllSlotsReset()]

            if len(available_colors) == 1:
                selected_color = list(available_colors)[0]
                dispatcher.utter_message(text=f"Bạn đã chọn {variant_name}. hiện tại {selected_color} là màu duy nhất bạn nhé.")
                return [SlotSet("variant_color", selected_color)]

            buttons = []
            for color_name in available_colors:
                buttons.append({
                    "title": f"{color_name}",
                    "payload": f'/inform{{"variant_color": "{color_name}"}}'
                })
            
            dispatcher.utter_message(
                text=f"Bạn đã chọn <b>{variant_name}</b>. Vui lòng chọn màu sắc:",
                buttons=buttons
            )
            return [SlotSet("product", product_name), SlotSet("variant_name", variant_name)]

        # 5. KỊCH BẢN 4: CHƯA CÓ CHI NHÁNH 
        found_variant = db_service.variants_collection.find_one({
            "_id": {"$in": variant_ids},
            "name": {"$regex": f"^{variant_name}$", "$options": "i"},
            "color": {"$elemMatch": {"colorName": {"$regex": f"^{variant_color}$", "$options": "i"}}}
        })

        if not found_variant:
            dispatcher.utter_message(text=f"Xin lỗi, tôi không tìm thấy phiên bản {variant_name} - {variant_color}.")
            return [AllSlotsReset()]
        
        variant_id = found_variant["_id"]
        variant_price = found_variant.get("price", 0)

        # 5.2. Parse số lượng (lấy từ slot "quantity", default là 1)
        try:
            quantity = int(float(quantity_str))
            if quantity <= 0: quantity = 1
        except (ValueError, TypeError):
            quantity = 1

        if not branch_id:   
            pipeline = [
                {"$match": {
                    "product": product_data["_id"],
                    "isActive": True,
                    "variants": {
                        "$elemMatch": {
                            "variantId": variant_id,
                            "stock": {"$gte": quantity} # Kiểm tra đủ số lượng
                        }
                    }
                }},
                {"$lookup": {
                    "from": "branches", "localField": "branch", "foreignField": "_id", "as": "branchInfo"
                }},
                {"$unwind": "$branchInfo"},
                {"$project": {
                    "_id": 0, "branch_id": "$branchInfo._id", "branch_name": "$branchInfo.name"
                }}
            ]
            available_branches = list(db_service.inventories_collection.aggregate(pipeline))

            if not available_branches:
                dispatcher.utter_message(text=f"Rất tiếc, sản phẩm {variant_name} - {variant_color} đã hết hàng hoặc không đủ số lượng {quantity} tại tất cả các chi nhánh.")
                return [AllSlotsReset()]
            
            if len(available_branches) == 1:
                branch_id = str(available_branches[0]["branch_id"])
            else:
                # Hiển thị buttons chọn chi nhánh
                buttons = []
                for branch in available_branches:
                    buttons.append({
                        "title": f"{branch['branch_name']}",
                        "payload": f'/inform{{"selected_branch_id": "{str(branch["branch_id"])}"}}'
                    })
                
                dispatcher.utter_message(
                    text=f"Sản phẩm này có sẵn tại các chi nhánh sau. Bạn muốn thêm vào giỏ hàng từ chi nhánh nào?",
                    buttons=buttons
                )
                return [
                    SlotSet("product", product_name),
                    SlotSet("variant_name", variant_name),
                    SlotSet("variant_color", variant_color),
                    SlotSet("quantity", quantity)
                ]
        
        payload = {
            "items": [{
                "product": str(product_data['_id']),
                "variant": str(variant_id),
                "color": variant_color, 
                "quantity": quantity,
                "price": variant_price,
                "branch": branch_id      
            }]
        }


        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = requests.post("http://localhost:8080/api/v1/carts", json=payload, headers=headers, timeout=10)
            
            if response.status_code in [200, 201]:
                dispatcher.utter_message(text=f"Đã thêm {quantity} x {product_name} ({variant_name} - {variant_color}) vào giỏ hàng thành công!")
            else:
                dispatcher.utter_message(text="Xin lỗi, đã có lỗi xảy ra khi thêm sản phẩm vào giỏ hàng.")
                print(f"Backend error: {response.status_code} - {response.text}")
        except Exception as e:
            dispatcher.utter_message(text="Đã có lỗi kết nối đến máy chủ. Vui lòng thử lại sau.")
            print(f"Error calling cart API: {e}")

        return [AllSlotsReset()]