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

            # 8. Tạo phản hồi HTML chuyên nghiệp
            if total_stock_all == 0:
                message = f"""
                <div style="font-family: sans-serif; border: 1px solid #ffebee; background-color: #fff5f5; border-radius: 8px; padding: 16px; max-width: 500px;">
                    <div style="display: flex; align-items: center; margin-bottom: 12px;">
                        <span style="font-size: 24px; margin-right: 10px;">❌</span>
                        <h3 style="margin: 0; color: #c62828; font-size: 16px; font-weight: 600;">Hết hàng</h3>
                    </div>
                    <p style="margin: 0; color: #333; font-size: 14px; line-height: 1.5;">
                        Rất tiếc! Hiện tại tôi không tìm thấy sản phẩm nào còn hàng {scope_message}.
                    </p>
                    <div style="margin-top: 12px; font-size: 13px; color: #666;">
                        Bạn có thể thử tìm sản phẩm khác hoặc liên hệ hotline để được hỗ trợ thêm.
                    </div>
                </div>
                """
                dispatcher.utter_message(text=message)
                return events_to_return

            # Nếu có hàng, build HTML chi tiết
            branch_details_html = ""
            for branch, items in branch_stock_map.items():
                if not items: continue

                # Group items by variant name & color to sum stock if needed, or just list them
                # items structure: [{'name': '128GB', 'color': 'Xanh', 'stock': 5}, ...]
                
                items_html = ""
                for item in items:
                    v_name = item['name']
                    v_color = item['color']
                    v_stock = item['stock']
                    
                    items_html += f"""
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px dashed #eee;">
                        <div style="display: flex; align-items: center;">
                            <span style="display: inline-block; width: 8px; height: 8px; background-color: #4caf50; border-radius: 50%; margin-right: 8px;"></span>
                            <span style="font-size: 13px; color: #333;">{v_name} - {v_color}</span>
                        </div>
                        <span style="font-size: 13px; font-weight: 600; color: #2e7d32; background-color: #e8f5e9; padding: 2px 8px; border-radius: 12px;">
                            Còn {v_stock}
                        </span>
                    </div>
                    """

                branch_details_html += f"""
                <div style="margin-bottom: 12px; background-color: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 10px;">
                    <div style="display: flex; align-items: center; margin-bottom: 8px;">
                        <span style="font-size: 16px; margin-right: 6px;">🏪</span>
                        <h4 style="margin: 0; font-size: 14px; font-weight: 600; color: #1f2937;">{branch}</h4>
                    </div>
                    <div style="padding-left: 4px;">
                        {items_html}
                    </div>
                </div>
                """

            message = f"""
            <div style="font-family: sans-serif; border: 1px solid #e0e0e0; background-color: #fff; border-radius: 8px; overflow: hidden; max-width: 500px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
                <div style="background-color: #d32f2f; padding: 12px 16px; display: flex; align-items: center; justify-content: space-between;">
                    <div style="display: flex; align-items: center; color: #fff;">
                        <span style="font-size: 20px; margin-right: 10px;">📦</span>
                        <h3 style="margin: 0; font-size: 16px; font-weight: 600;">Thông tin tồn kho</h3>
                    </div>
                    <span style="background-color: rgba(255,255,255,0.2); color: #fff; font-size: 12px; padding: 4px 8px; border-radius: 4px;">
                        Tổng: {total_stock_all}
                    </span>
                </div>
                
                <div style="padding: 16px;">
                    <p style="margin: 0 0 16px 0; color: #555; font-size: 14px; line-height: 1.5;">
                        Dưới đây là tình trạng hàng {scope_message}:
                    </p>
                    
                    {branch_details_html}
                    
                    <div style="margin-top: 16px; font-size: 12px; color: #888; text-align: center; font-style: italic;">
                        * Số lượng có thể thay đổi theo thời gian thực.
                    </div>
                </div>
            </div>
            """
            
            # Tạo buttons
            buttons = [
                {"title": "🛒 Đặt hàng ngay", "payload": "/order"},
                {"title": "🔍 Xem chi tiết sản phẩm", "payload": f'/ask_product_info{{"product_name": "{product_name_proper}"}}'}
            ]
            
            dispatcher.utter_message(text=message, buttons=buttons)

        except Exception as e:
            logger.error(f"Lỗi trong ActionCheckStock: {e}")
            dispatcher.utter_message(text="Xin lỗi, tôi gặp lỗi khi kiểm tra kho, bạn vui lòng thử lại sau nhé.")
            
        return events_to_return