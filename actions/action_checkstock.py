import pymongo
import logging
from rasa_sdk import Action, Tracker
from bson import ObjectId
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from typing import Any, Text, Dict, List
import re
from utils.database import DatabaseService
from utils.product_pipelines import build_search_pipeline
from collections import defaultdict 

# Thiết lập logger
logger = logging.getLogger(__name__)

class ActionCheckStock(Action):
    def name(self) -> Text:
        return "action_check_stock"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # 1. Lấy thông tin từ các slots (3 cấp độ)
        product_name = tracker.get_slot("product_name")
        variant_name_group = tracker.get_slot("variant_name") # "128GB"
        variant_color = tracker.get_slot("variant_color")   # "Xanh"
        branch_name = tracker.get_slot("branch_name") 

        if not product_name:
            dispatcher.utter_message(text="Bạn muốn kiểm tra tồn kho cho sản phẩm nào ạ?")
            return []
        
        # Reset các slot lọc khi chạy xong
        events_to_return = [
            SlotSet("variant_name", None),
            SlotSet("variant_color", None),
            SlotSet("branch_name", None)
        ]
        
        try:
            db = DatabaseService()
            
            # 2. Tìm sản phẩm và lấy danh sách variant_ids
            pipeline_search = build_search_pipeline(product_name)
            product_doc_list = list(db.products_collection.aggregate(pipeline_search))

            if not product_doc_list:
                dispatcher.utter_message(text=f"Xin lỗi, tôi không tìm thấy sản phẩm nào có tên là '{product_name}'.")
                return events_to_return
            
            product_doc = product_doc_list[0]
            product_id = product_doc["_id"]
            product_name_proper = product_doc.get("name", product_name)
            # Lấy list IDs các variant liên quan đến sản phẩm
            variant_ids_list = product_doc.get("variants", [])
            if not variant_ids_list:
                dispatcher.utter_message(text=f"Sản phẩm {product_name_proper} chưa có phiên bản nào.")
                return events_to_return

            # 3. Tạo map tra cứu ID -> Tên (ví dụ: ObjectId('aaa') -> "128GB")
            variants_map = {}
            variant_docs = db.variants_collection.find(
                {"_id": {"$in": variant_ids_list}}, 
                {"_id": 1, "name": 1}
            )
            for v in variant_docs:
                variants_map[v["_id"]] = v.get("name", "N/A")

            # 4. Xác định bộ lọc (target_variant_id, target_color)
            target_variant_id = None
            target_color = variant_color # Có thể là None
            scope_message = f"của sản phẩm <strong>{product_name_proper}</strong>"
            
            if variant_name_group:
                # Tìm ID cho "128GB"
                target_variant_id = next(
                    (vid for vid, vname in variants_map.items() if vname.lower() == variant_name_group.lower()), 
                    None
                )
                if not target_variant_id:
                    dispatcher.utter_message(text=f"Không tìm thấy phiên bản '{variant_name_group}' cho sản phẩm này.")
                    return events_to_return
                scope_message += f" (phiên bản <strong>{variant_name_group}</strong>)"

            if target_color:
                scope_message += f" (màu <strong>{target_color}</strong>)"

            # 5. Xây dựng pipeline truy vấn tồn kho
            inventory_pipeline = [
                {"$match": {"product": product_id, "isActive": True, "variants.stock": {"$gt": 0}}}
            ]
            
            if branch_name:
                branch_doc = db.branches_collection.find_one({
                    "name": {"$regex": f"^{re.escape(branch_name)}$", "$options": "i"}
                })
                if not branch_doc:
                    dispatcher.utter_message(text=f"Không tìm thấy chi nhánh '{branch_name}'.")
                    return events_to_return
                
                inventory_pipeline[0]["$match"]["branch"] = branch_doc["_id"]
                scope_message += f" tại chi nhánh <strong>{branch_doc.get('name', branch_name)}</strong>"
            
            # Thêm $lookup chi nhánh
            inventory_pipeline.extend([
                {"$lookup": {"from": "branches", "localField": "branch", "foreignField": "_id", "as": "branchInfo"}},
                {"$unwind": "$branchInfo"}
            ])

            # 6. Chạy pipeline
            inventory_docs = list(db.inventories_collection.aggregate(inventory_pipeline))

            if not inventory_docs:
                dispatcher.utter_message(text=f"Rất tiếc, tôi không tìm thấy hàng tồn kho nào {scope_message}.")
                return events_to_return 

            branch_stock_map = defaultdict(list)
            total_stock_all = 0

            for doc in inventory_docs:
                branch_name_from_doc = doc.get("branchInfo", {}).get("name", "N/A")
                
                for variant in doc.get("variants", []):
                    v_stock = variant.get("stock", 0)
                    if v_stock <= 0:
                        continue
                        
                    v_id = variant.get("variantId")
                    v_color = variant.get("variantColor")
                    
                    # Áp dụng bộ lọc
                    match_id = (target_variant_id is None) or (v_id == target_variant_id)
                    match_color = (target_color is None) or (target_color.lower() in v_color.lower())
                    
                    if match_id and match_color:
                        v_name = variants_map.get(v_id, "Phiên bản không rõ")
                        
                        branch_stock_map[branch_name_from_doc].append({
                            "name": v_name,
                            "color": v_color,
                            "stock": v_stock
                        })
                        total_stock_all += v_stock

            # 8. Tạo phản hồi
            if total_stock_all == 0:
                message = f"""<div class="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                                <h4 class="font-bold text-gray-800 mb-2">❌ Hết hàng</h4>
                                <p class="text-gray-700">
                                    Rất tiếc! Tôi không tìm thấy sản phẩm nào còn hàng {scope_message}.
                                </p>
                                </div>"""
                dispatcher.utter_message(text=message)
                return events_to_return

            # Nếu có hàng, build HTML
            branch_details_html = []
            for branch, items in branch_stock_map.items():
                if not items: continue # Bỏ qua chi nhánh không có hàng (sau khi lọc)

               
                branch_total_stock = 0
                
                grouped_items = defaultdict(int)
                for item in items:
                    grouped_items[(item['name'], item['color'])] += item['stock']
                    branch_total_stock += item['stock']


                branch_details_html.append(
                    f"""<div class='mt-3 p-3 bg-gray-50 rounded border border-gray-200'>
                           <h5 class='font-bold text-blue-600'>{branch} (Còn: {branch_total_stock})</h5>
                       </div>"""
                )

            message = f"""<div class="p-4 bg-white border border-gray-200 rounded-lg">
                            <h4 class="font-bold text-gray-800 mb-2"> Thông tin tồn kho</h4>
                            <p class="text-gray-700">
                                Tìm thấy tổng cộng <strong class="text-orange-600">{total_stock_all}</strong> sản phẩm {scope_message}.
                            </p>
                            <p class="mt-3 mb-2 font-medium text-gray-800">Sản phẩm còn hàng tại các chi nhánh:</p>
                            {''.join(branch_details_html)}
                            </div>"""
            dispatcher.utter_message(text=message)

        except Exception as e:
            logger.error(f"Lỗi trong ActionCheckStock: {e}")
            dispatcher.utter_message(text="Xin lỗi, tôi gặp lỗi khi kiểm tra kho, bạn vui lòng thử lại sau nhé.")
            
        return events_to_return