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

        # Lấy thông tin sản phẩm
        pipeline1 = build_search_pipeline(product_1)
        pipeline2 = build_search_pipeline(product_2)
        
        result1 = list(db.products_collection.aggregate(pipeline1))
        result2 = list(db.products_collection.aggregate(pipeline2))
        
        product_1_info = result1[0] if result1 else None
        product_2_info = result2[0] if result2 else None

        if not product_1_info:
            dispatcher.utter_message(text=f"Không tìm thấy thông tin của sản phẩm '{product_1}'")
            return [AllSlotsReset()]
        if not product_2_info:
            dispatcher.utter_message(text=f"Không tìm thấy thông tin của sản phẩm '{product_2}'")
            return [AllSlotsReset()]
        
        # Lấy thông tin category và brand trực tiếp từ kết quả pipeline
        category1 = product_1_info.get("category", {})
        category2 = product_2_info.get("category", {})
        
        brand1 = product_1_info.get("brand", {})
        brand2 = product_2_info.get("brand", {})

        # Lấy variants
        variants1 = list(db.variants_collection.find({"_id": {"$in": product_1_info.get("variants", [])}}))
        variants2 = list(db.variants_collection.find({"_id": {"$in": product_2_info.get("variants", [])}}))

        # Kiểm tra xem 2 sản phẩm có cùng danh mục không
        same_category = (category1 and category2 and 
                        category1.get("_id") == category2.get("_id"))
        if same_category:
            # So sánh chi tiết thông số kỹ thuật
            html_content = self._build_detailed_comparison_html(
                product_1_info, product_2_info,
                category1, brand1, brand2,
                variants1, variants2
            )
        else:
            # So sánh cơ bản
            html_content = self._build_basic_comparison_html(
                product_1_info, product_2_info,
                category1, category2,
                brand1, brand2,
                variants1, variants2
            )
        
        dispatcher.utter_message(text=html_content, html=True)
        
        return [AllSlotsReset()]

    def _build_basic_comparison_html(
        self,
        product_1: Dict,
        product_2: Dict,
        category1: Dict,
        category2: Dict,
        brand1: Dict,
        brand2: Dict,
        variants1: List[Dict],
        variants2: List[Dict]
    ) -> Text:
        """So sánh cơ bản khi 2 sản phẩm khác danh mục"""
        
        p1_name = product_1.get('name', 'Sản phẩm 1')
        p2_name = product_2.get('name', 'Sản phẩm 2')
        
        # Giá
        p1_price = format_vnd(variants1[0].get('price', 0)) if variants1 else format_vnd(product_1.get('price', 0))
        p2_price = format_vnd(variants2[0].get('price', 0)) if variants2 else format_vnd(product_2.get('price', 0))
        
        # Brand
        b1_name = brand1.get('name', '—') if brand1 else '—'
        b2_name = brand2.get('name', '—') if brand2 else '—'
        
        # Category
        c1_name = category1.get('name', '—') if category1 else '—'
        c2_name = category2.get('name', '—') if category2 else '—'

        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; color: #1a1a1a; max-width: 700px;">
            <div style="padding: 12px; margin-bottom: 12px; background: #fff; border: 1px solid #e5e5e5; border-radius: 8px;">
                <h4 style="margin: 0 0 15px 0; font-size: 16px; color: #333; border-bottom: 2px solid #eee; padding-bottom: 8px;">So sánh sản phẩm</h4>
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background-color: #f9f9f9;">
                            <th style="padding: 8px; text-align: left; font-size: 14px; font-weight: 600; border-bottom: 1px solid #ddd;"></th>
                            <th style="padding: 8px; text-align: center; font-size: 14px; font-weight: 600; border-bottom: 1px solid #ddd;">{p1_name}</th>
                            <th style="padding: 8px; text-align: center; font-size: 14px; font-weight: 600; border-bottom: 1px solid #ddd;">{p2_name}</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td style="padding: 8px; font-size: 13px; color: #666; border-bottom: 1px solid #f0f0f0;">Danh mục</td>
                            <td style="padding: 8px; text-align: center; font-size: 13px; border-bottom: 1px solid #f0f0f0;">{c1_name}</td>
                            <td style="padding: 8px; text-align: center; font-size: 13px; border-bottom: 1px solid #f0f0f0;">{c2_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; font-size: 13px; color: #666; border-bottom: 1px solid #f0f0f0;">Thương hiệu</td>
                            <td style="padding: 8px; text-align: center; font-size: 13px; border-bottom: 1px solid #f0f0f0;">{b1_name}</td>
                            <td style="padding: 8px; text-align: center; font-size: 13px; border-bottom: 1px solid #f0f0f0;">{b2_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; font-size: 13px; color: #666;">Giá bán</td>
                            <td style="padding: 8px; text-align: center; font-size: 14px; font-weight: 600; color: #d9534f;">{p1_price}</td>
                            <td style="padding: 8px; text-align: center; font-size: 14px; font-weight: 600; color: #d9534f;">{p2_price}</td>
                        </tr>
                    </tbody>
                </table>
                <p style="margin: 10px 0 0 0; font-size: 12px; color: #999; font-style: italic;">* Hai sản phẩm thuộc danh mục khác nhau nên chỉ so sánh thông tin cơ bản</p>
            </div>
        </div>
        """
        return html

    def _build_detailed_comparison_html(
        self,
        product_1: Dict,
        product_2: Dict,
        category: Dict,
        brand1: Dict,
        brand2: Dict,
        variants1: List[Dict],
        variants2: List[Dict]
    ) -> Text:
        """So sánh chi tiết thông số kỹ thuật khi 2 sản phẩm cùng danh mục"""
        
        p1_name = product_1.get('name', 'Sản phẩm 1')
        p2_name = product_2.get('name', 'Sản phẩm 2')
        
        # Giá
        p1_price = format_vnd(variants1[0].get('price', 0)) if variants1 else format_vnd(product_1.get('price', 0))
        p2_price = format_vnd(variants2[0].get('price', 0)) if variants2 else format_vnd(product_2.get('price', 0))
        
        # Brand
        b1_name = brand1.get('name', '—') if brand1 else '—'
        b2_name = brand2.get('name', '—') if brand2 else '—'
        
        # Category
        category_name = category.get('name', 'Sản phẩm') if category else 'Sản phẩm'

        # Lấy thông số kỹ thuật (ưu tiên specifications, fallback sang attributes)
        raw_specs1 = product_1.get('specifications') or product_1.get('attributes') or {}
        raw_specs2 = product_2.get('specifications') or product_2.get('attributes') or {}
        
        # Helper function to normalize specs into map (key -> value) and labels (key -> label)
        def normalize_specs(raw_specs):
            spec_map = {}
            spec_labels = {}
            if isinstance(raw_specs, list):
                for item in raw_specs:
                    # Ưu tiên 'key' làm định danh, nếu không có thì dùng 'name'
                    k = item.get('key', item.get('name'))
                    v = item.get('value')
                    
                    # Convert boolean True to "Có"
                    if v is True:
                        v = "Có"
                        
                    # Ưu tiên 'name' làm nhãn hiển thị, nếu không có thì dùng key
                    l = item.get('name', k)
                    
                    if k:
                        k_str = str(k)
                        spec_map[k_str] = str(v) if v is not None else '—'
                        spec_labels[k_str] = str(l) if l else k_str
            elif isinstance(raw_specs, dict):
                for k, v in raw_specs.items():
                    k_str = str(k)
                    
                    # Convert boolean True to "Có"
                    if v is True:
                        v = "Có"
                        
                    spec_map[k_str] = str(v) if v is not None else '—'
                    spec_labels[k_str] = k_str # Với dict, key cũng là label
            return spec_map, spec_labels

        specs1, labels1 = normalize_specs(raw_specs1)
        specs2, labels2 = normalize_specs(raw_specs2)

        # Lấy cấu hình fields từ category
        config_fields = category.get('configFields', {})
        extra_fields = config_fields.get('extraFields', [])
        
        spec_rows = ""
        
        if extra_fields:
            # Sử dụng cấu hình từ category để hiển thị
            for field in extra_fields:
                field_name = field.get('name')
                field_label = field.get('label')
                
                if not field_name:
                    continue
                    
                # Lấy giá trị từ specs đã chuẩn hóa
                val1 = specs1.get(field_name)
                if val1 is None:
                     # Fallback check attributes directly if needed
                     attrs1 = product_1.get('attributes', {})
                     val1 = attrs1.get(field_name, '—')
                
                val2 = specs2.get(field_name)
                if val2 is None:
                     attrs2 = product_2.get('attributes', {})
                     val2 = attrs2.get(field_name, '—')

                if val1 == '—' and val2 == '—':
                    continue

                spec_rows += f"""
                    <tr>
                        <td style="padding: 8px; font-size: 13px; color: #666; border-bottom: 1px solid #f0f0f0;">{field_label}</td>
                        <td style="padding: 8px; text-align: center; font-size: 13px; border-bottom: 1px solid #f0f0f0;">{val1}</td>
                        <td style="padding: 8px; text-align: center; font-size: 13px; border-bottom: 1px solid #f0f0f0;">{val2}</td>
                    </tr>"""
        else:
            # Fallback: Thu thập tất cả các key specs từ cả 2 sản phẩm
            all_spec_keys = set(specs1.keys()) | set(specs2.keys())
            
            for spec_key in sorted(all_spec_keys):
                # Lấy label từ dữ liệu sản phẩm (ưu tiên p1, rồi p2, rồi key)
                spec_display_name = labels1.get(spec_key) or labels2.get(spec_key) or spec_key
                
                spec_value1 = specs1.get(spec_key, '—')
                spec_value2 = specs2.get(spec_key, '—')
                
                spec_rows += f"""
                        <tr>
                            <td style="padding: 8px; font-size: 13px; color: #666; border-bottom: 1px solid #f0f0f0;">{spec_display_name}</td>
                            <td style="padding: 8px; text-align: center; font-size: 13px; border-bottom: 1px solid #f0f0f0;">{spec_value1}</td>
                            <td style="padding: 8px; text-align: center; font-size: 13px; border-bottom: 1px solid #f0f0f0;">{spec_value2}</td>
                        </tr>"""

        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; color: #1a1a1a; max-width: 700px;">
            <div style="padding: 12px; margin-bottom: 12px; background: #fff; border: 1px solid #e5e5e5; border-radius: 8px;">
                <h4 style="margin: 0 0 15px 0; font-size: 16px; color: #333; border-bottom: 2px solid #eee; padding-bottom: 8px;">So sánh chi tiết - {category_name}</h4>
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background-color: #f9f9f9;">
                            <th style="padding: 8px; text-align: left; font-size: 14px; font-weight: 600; border-bottom: 1px solid #ddd;">Thông số</th>
                            <th style="padding: 8px; text-align: center; font-size: 14px; font-weight: 600; border-bottom: 1px solid #ddd;">{p1_name}</th>
                            <th style="padding: 8px; text-align: center; font-size: 14px; font-weight: 600; border-bottom: 1px solid #ddd;">{p2_name}</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td style="padding: 8px; font-size: 13px; color: #666; border-bottom: 1px solid #f0f0f0;">Giá bán</td>
                            <td style="padding: 8px; text-align: center; font-size: 14px; font-weight: 600; color: #d9534f; border-bottom: 1px solid #f0f0f0;">{p1_price}</td>
                            <td style="padding: 8px; text-align: center; font-size: 14px; font-weight: 600; color: #d9534f; border-bottom: 1px solid #f0f0f0;">{p2_price}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; font-size: 13px; color: #666; border-bottom: 1px solid #f0f0f0;">Thương hiệu</td>
                            <td style="padding: 8px; text-align: center; font-size: 13px; border-bottom: 1px solid #f0f0f0;">{b1_name}</td>
                            <td style="padding: 8px; text-align: center; font-size: 13px; border-bottom: 1px solid #f0f0f0;">{b2_name}</td>
                        </tr>
                        {spec_rows}
                    </tbody>
                </table>
            </div>
        </div>
        """
        return html
