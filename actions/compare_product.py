from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import AllSlotsReset
from utils.database import DatabaseService
from utils.format_currentcy import format_vnd
from utils.product_pipelines import build_search_pipeline

class ActionCompareProducts(Action):
    def name(self) -> Text:
        return "action_compare_products"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        
        product_1 = tracker.get_slot("product_1")
        product_2 = tracker.get_slot("product_2")
        
        if not product_1 or not product_2:
            dispatcher.utter_message(
                text="Vui lòng cung cấp tên của hai sản phẩm để so sánh. Ví dụ: iPhone 16 và Galaxy S24"
            )
            return []

        db = DatabaseService()

        product_1_info = db.products_collection.aggregate(build_search_pipeline(product_1))
        product_2_info = db.products_collection.aggregate(build_search_pipeline(product_2))

        if not product_1_info:
            dispatcher.utter_message(text=f"Không tìm thấy thông tin của sản phẩm {product_1}")
            return []
        if not product_2_info:
            dispatcher.utter_message(text=f"Không tìm thấy thông tin của sản phẩm {product_2}")
            return []

        variants1 = list(db.variants_collection.find({"_id": {"$in": product_1_info.get("variants", [])}}))
        variants2 = list(db.variants_collection.find({"_id": {"$in": product_2_info.get("variants", [])}}))

        brand1 = db.brands_collection.find_one({"_id": product_1_info["brand"]})
        brand2 = db.brands_collection.find_one({"_id": product_2_info["brand"]})

        html_content = self._build_simple_comparison_html(
            product_1_info, product_2_info,
            brand1, brand2,
            variants1, variants2
        )
        
        dispatcher.utter_message(text=html_content, html=True)
        
        return [AllSlotsReset()]


    def _build_simple_comparison_html(
        self,
        product_1: Dict,
        product_2: Dict,
        brand1: Dict,
        brand2: Dict,
        variants1: List[Dict],
        variants2: List[Dict]
    ) -> Text:
        
        p1_name = product_1.get('name', 'Sản phẩm 1')
        p2_name = product_2.get('name', 'Sản phẩm 2')
        p1_price = format_vnd(variants1[0].get('price', 0)) if variants1 else format_vnd(product_1.get('price', 0))
        p2_price = format_vnd(variants2[0].get('price', 0)) if variants2 else format_vnd(product_2.get('price', 0))
        b1_name = brand1.get('name', '—') if brand1 else '—'
        b2_name = brand2.get('name', '—') if brand2 else '—'

        variants1_str = "<br>".join([
            f"{v.get('name', '')}: <strong>{format_vnd(v.get('price', 0))}</strong>"
            for v in variants1
        ]) if variants1 else 'Không có'
        variants2_str = "<br>".join([
            f"{v.get('name', '')}: <strong>{format_vnd(v.get('price', 0))}</strong>"
            for v in variants2
        ]) if variants2 else 'Không có'

        html = f"""
        <div style="font-family: Arial, sans-serif; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
            <table style="width:100%; border-collapse: collapse;">
                <thead style="background-color: #f8f9fa;">
                    <tr>
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e0e0e0; font-size: 14px; color: #333;">So sánh nhanh</th>
                        <th style="padding: 12px; text-align: center; border-bottom: 2px solid #e0e0e0; font-size: 14px; color: #007bff;">{p1_name}</th>
                        <th style="padding: 12px; text-align: center; border-bottom: 2px solid #e0e0e0; font-size: 14px; color: #28a745;">{p2_name}</th>
                    </tr>
                </thead>
                <tbody>
                    <tr style="border-bottom: 1px solid #f0f0f0;">
                        <td style="padding: 10px; font-weight: bold; color: #555;">Giá bán</td>
                        <td style="padding: 10px; text-align: center; color: #d9534f; font-weight: bold; font-size: 16px;">{p1_price}</td>
                        <td style="padding: 10px; text-align: center; color: #d9534f; font-weight: bold; font-size: 16px;">{p2_price}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #f0f0f0;">
                        <td style="padding: 10px; font-weight: bold; color: #555;">Thương hiệu</td>
                        <td style="padding: 10px; text-align: center;">{b1_name}</td>
                        <td style="padding: 10px; text-align: center;">{b2_name}</td>
                    </tr>
                    <tr style="background-color: #fdfdfd;">
                        <td style="padding: 10px; font-weight: bold; color: #555; vertical-align: top;">Phiên bản</td>
                        <td style="padding: 10px; text-align: center; font-size: 13px; line-height: 1.5;">{variants1_str}</td>
                        <td style="padding: 10px; text-align: center; font-size: 13px; line-height: 1.5;">{variants2_str}</td>
                    </tr>
                </tbody>
            </table>
        </div>
        """
        return html
