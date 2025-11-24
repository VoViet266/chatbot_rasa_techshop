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
        try:
            # Find active promotions
            promotions = list(db.promotions_collection.find({
                "isActive": True,
                "startDate": {"$lte": now},
                "endDate": {"$gte": now}
            }))
            
            if not promotions:
                dispatcher.utter_message(text="Hiện tại shop chưa có chương trình khuyến mãi nào đang diễn ra ạ.")
                return []
                
            html_parts = [
                """
                <div style="background-color: #fff; border: 1px solid #e0e0e0; border-radius: 10px; padding: 16px; margin-bottom: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); font-family: sans-serif;">
                    <div style="display: flex; align-items: center; margin-bottom: 12px; border-bottom: 1px solid #f0f0f0; padding-bottom: 8px;">
                        <h3 style="color: #d32f2f; margin: 0; font-size: 16px; font-weight: bold;">Khuyến Mãi Đang Diễn Ra</h3>
                    </div>
                """
            ]
            
            for promo in promotions:
                value_str = f"{promo.get('value')}%" if promo.get('valueType') == 'PERCENT' else f"{promo.get('value'):,}đ"
                end_date = promo.get('endDate').strftime('%d/%m/%Y')
                
                promo_html = f"""
                <div style="background-color: #fff5f5; border: 1px dashed #ffcdd2; border-radius: 8px; padding: 12px; margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div>
                            <div style="font-weight: bold; color: #b71c1c; font-size: 14px; margin-bottom: 4px;">{promo.get('title')}</div>
                            <div style="font-size: 13px; color: #555;">{promo.get('description', '')}</div>
                        </div>
                        <div style="background-color: #d32f2f; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; white-space: nowrap;">
                            Giảm {value_str}
                        </div>
                    </div>
                    <div style="margin-top: 8px; font-size: 12px; color: #757575; display: flex; align-items: center;">
                        <span style="margin-right: 4px;">⏳</span>
                        HSD: {end_date}
                    </div>
                </div>
                """
                html_parts.append(promo_html)
            
            html_parts.append("</div>")
            
            dispatcher.utter_message(text="\n".join(html_parts))
            
        except Exception as e:
            print(f"Error checking promotions: {e}")
            dispatcher.utter_message(text="Có lỗi xảy ra khi tra cứu khuyến mãi.")
            
        return []
