from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from utils.database import DatabaseService
from datetime import datetime

class ActionCheckPromotion(Action):
    def name(self) -> Text:
        return "action_check_promotion"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        db = DatabaseService()
        now = datetime.now()
        
        # 1. Xử lý logic tìm kiếm Category
        category_name = tracker.get_slot("category")
        cat_filter = {}
        display_title = "Tất Cả Sản Phẩm"

        if category_name:
            # Tìm category theo regex (không phân biệt hoa thường)
            category = db.categories_collection.find_one(
                {"name": {"$regex": f"^{category_name}$", "$options": "i"}}
            )
            if category:
                display_title = category["name"]
                cat_filter = {
                    "$or": [
                        {"categories": category["_id"]},
                        {"categories": {"$exists": False}},
                        {"categories": []},
                        {"categories": None}
                    ]
                }

        # 2. Query Database
        try:
            query = {
                "isActive": True,
                "startDate": {"$lte": now},
                "endDate": {"$gte": now}
            }
            if cat_filter:
                query.update(cat_filter)

            promotions = list(db.promotions_collection.find(query))
            
            if not promotions:
                dispatcher.utter_message(text=f"Hiện tại chưa có khuyến mãi nào cho {display_title} ạ.")
                return []

            
            
            # Tạo danh sách HTML items
            list_items_html = ""
            for p in promotions:
                val = f"{p.get('value')}%" if p.get('valueType') == 'percent' else f"{p.get('value'):,}đ"
                end_date = p.get('endDate').strftime('%d/%m')
                
                list_items_html += f"""
                <div style="display:flex; justify-content:space-between; align-items:center; background:#fff5f5; border:1px dashed #ffcdd2; border-radius:8px; padding:10px; margin-bottom:8px;">
                    <div style="flex:1;">
                        <div style="color:#b71c1c; font-weight:bold; font-size:14px;">{p.get('title')}</div>
                        <div style="font-size:12px; color:#666;">Hạn đến: {end_date}</div>
                    </div>
                    <div style="color:#b71c1c; font-size:12px; font-weight:bold; white-space:nowrap; margin-left:8px;">Giảm {val}</div>
                </div>
                """

            # Ghép thành message hoàn chỉnh
            html_message = f"""
            <div style="background:#fff; border:1px solid #e0e0e0; border-radius:10px; padding:15px; font-family:sans-serif;">
                <h3 style="color:#d32f2f; margin:0 0 10px 0; font-size:16px; font-weight:bold; border-bottom:1px solid #f0f0f0; padding-bottom:8px;">Khuyến Mãi: {display_title}</h3>
                {list_items_html}
            </div>
            """
            
            dispatcher.utter_message(text=html_message)

        except Exception as e:
            print(f"Error checking promotions: {e}")
            dispatcher.utter_message(text="Có lỗi xảy ra khi tra cứu khuyến mãi.")
            
        return []