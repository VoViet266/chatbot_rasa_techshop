from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from typing import Any, Text, Dict, List
from utils.database import DatabaseService


class ActionAskCategoryList(Action):
    """Hiển thị danh sách các danh mục sản phẩm"""
    
    def name(self) -> Text:
        return "action_ask_category_list"
    
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        db_service = DatabaseService()
        
        try:
            # Get all active categories
            categories = list(db_service.categories_collection.find(
                {"isDeleted": {"$ne": True}},
                {"name": 1, "description": 1}
            ).sort("name", 1))
            
            if not categories:
                dispatcher.utter_message(text="Hiện tại shop chưa có danh mục sản phẩm nào.")
                return []
            
            # Build HTML response
            categories_html = ""
            for cat in categories:
                cat_name = cat.get("name", "")
                cat_desc = cat.get("description", "")
                desc_html = f'<div style="color: #6b7280; font-size: 11px; margin-top: 2px;">{cat_desc}</div>' if cat_desc else ''
                categories_html += f"""
                <div style="padding: 8px 0; border-bottom: 1px solid #f3f4f6;">
                    <div style="font-weight: 600; color: #111827; font-size: 13px;">{cat_name}</div>
                    {desc_html}
                </div>
                """
            
            html = f"""
            <div style="
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                padding: 16px;
                margin: 8px 0;
                background: #ffffff;
                font-family: system-ui, -apple-system, sans-serif;
                max-width: 320px;
                min-width: 320px;
                box-shadow: 0 1px 2px rgba(0,0,0,0.05);
            ">
                <div style="font-size: 14px; font-weight: 700; color: #111827; margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #f3f4f6;">
                     Danh mục sản phẩm
                </div>
                <div style="max-height: 300px; overflow-y: auto;">
                    {categories_html}
                </div>
                <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #f3f4f6; text-align: center; font-size: 12px; color: #6b7280;">
                    Tổng {len(categories)} danh mục
                </div>
            </div>
            """
            
            dispatcher.utter_message(text=html)
            
        except Exception as e:
            print(f"Error in ActionAskCategoryList: {e}")
            dispatcher.utter_message(text="Xin lỗi, đã có lỗi khi lấy danh sách danh mục.")
        
        return []


class ActionAskBrandList(Action):
    """Hiển thị danh sách các nhãn hiệu"""
    
    def name(self) -> Text:
        return "action_ask_brand_list"
    
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        db_service = DatabaseService()
        
        try:
            # Get all active brands
            brands = list(db_service.brands_collection.find(
                {"isDeleted": {"$ne": True}},
                {"name": 1, "description": 1, "logo": 1}
            ).sort("name", 1))
            
            if not brands:
                dispatcher.utter_message(text="Hiện tại shop chưa có nhãn hiệu nào.")
                return []
            
            # Build HTML response
            brands_html = ""
            for brand in brands:
                brand_name = brand.get("name", "")
                brand_desc = brand.get("description", "")
                logo = brand.get("logo", "")
                
                # Build logo HTML - Extract onerror to avoid backslash in f-string
                if logo:
                    onerror_attr = "this.style.display='none'"
                    logo_html = f'<img src="{logo}" style="max-width: 100%; max-height: 100%; object-fit: contain;" onerror="{onerror_attr}">'
                else:
                    logo_html = f'<span style="font-size: 16px; font-weight: 700; color: #9ca3af;">{brand_name[0]}</span>'
                
                # Build description HTML
                desc_html = f'<div style="color: #6b7280; font-size: 11px; margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{brand_desc}</div>' if brand_desc else ''
                
                brands_html += f"""
                <div style="display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid #f3f4f6;">
                    <div style="width: 40px; height: 40px; background: #f9fafb; border-radius: 4px; display: flex; align-items: center; justify-content: center; margin-right: 10px; flex-shrink: 0;">
                        {logo_html}
                    </div>
                    <div style="flex: 1; min-width: 0;">
                        <div style="font-weight: 600; color: #111827; font-size: 13px;">{brand_name}</div>
                        {desc_html}
                    </div>
                </div>
                """
            
            html = f"""
            <div style="
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                padding: 16px;
                margin: 8px 0;
                background: #ffffff;
                font-family: system-ui, -apple-system, sans-serif;
                max-width: 320px;
                min-width: 320px;
                box-shadow: 0 1px 2px rgba(0,0,0,0.05);
            ">
                <div style="font-size: 14px; font-weight: 700; color: #111827; margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #f3f4f6;">
                    Nhãn hiệu
                </div>
                <div style="max-height: 300px; overflow-y: auto;">
                    {brands_html}
                </div>
                <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #f3f4f6; text-align: center; font-size: 12px; color: #6b7280;">
                    Tổng {len(brands)} nhãn hiệu
                </div>
            </div>
            """
            
            dispatcher.utter_message(text=html)
            
        except Exception as e:
            print(f"Error in ActionAskBrandList: {e}")
            dispatcher.utter_message(text="Xin lỗi, đã có lỗi khi lấy danh sách nhãn hiệu.")
        
        return []


class ActionAskBrandInfo(Action):
    """Hiển thị thông tin chi tiết về một nhãn hiệu cụ thể"""
    
    def name(self) -> Text:
        return "action_ask_brand_info"
    
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        db_service = DatabaseService()
        
        # Get brand entity from user message
        brand_name = next(tracker.get_latest_entity_values("brand"), None)
        
        if not brand_name:
            dispatcher.utter_message(text="Bạn muốn biết thông tin về nhãn hiệu nào?")
            return []
        
        try:
            # Find brand in database
            brand = db_service.brands_collection.find_one({
                "name": {"$regex": f"^{brand_name}$", "$options": "i"},
                "isDeleted": {"$ne": True}
            })
            
            if not brand:
                dispatcher.utter_message(
                    text=f"Xin lỗi, shop hiện không có nhãn hiệu '{brand_name}'. Bạn có thể xem danh sách các nhãn hiệu khác bằng cách hỏi 'Có những hãng nào?'"
                )
                return []
            
            # Get brand info
            brand_id = brand.get("_id")
            brand_desc = brand.get("description", "")
            brand_logo = brand.get("logo", "")
            
            # Count products of this brand
            product_count = db_service.products_collection.count_documents({
                "brand": brand_id,
                "isDeleted": {"$ne": True}
            })
            
            # Get some sample products (top 3)
            sample_products = list(db_service.products_collection.find(
                {"brand": brand_id, "isDeleted": {"$ne": True}},
                {"name": 1, "price": 1, "discount": 1, "variants": 1}
            ).limit(3))
            
            # Build sample products HTML
            products_html = ""
            if sample_products:
                for product in sample_products:
                    prod_name = product.get("name", "")
                    if len(prod_name) > 30:
                        prod_name = prod_name[:27] + "..."
                    
                    # Get price from product or first variant
                    price = product.get("price", 0)
                    if not price:
                        variants = product.get("variants", [])
                        if variants and len(variants) > 0:
                            variant_id = variants[0]
                            # Variant is stored as ObjectId reference, need to fetch it
                            variant = db_service.variants_collection.find_one({"_id": variant_id})
                            if variant:
                                price = variant.get("price", 0)
                    products_html += f"""
                    <div style="padding: 6px 0; border-bottom: 1px solid #f3f4f6; font-size: 12px;">
                        <div style="color: #374151; font-weight: 500;">{prod_name}</div>
                        <div style="color: #d32f2f; font-weight: 600; margin-top: 2px;">{price:,.0f}₫</div>
                    </div>
                    """
            
            # Build logo HTML - Extract onerror to avoid backslash in f-string
            if brand_logo:
                onerror_attr = "this.style.display='none'"
                logo_html = f'<img src="{brand_logo}" style="max-width: 100%; max-height: 100%; object-fit: contain;" onerror="{onerror_attr}">'
            else:
                logo_html = f'<span style="font-size: 20px; font-weight: 700; color: #9ca3af;">{brand_name[0]}</span>'
            
            # Build description HTML
            desc_section = f'<div style="margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #f3f4f6;"><div style="font-size: 12px; color: #6b7280; line-height: 1.5;">{brand_desc}</div></div>' if brand_desc else ''
            
            # Build products section HTML
            products_section = f'<div style="margin-bottom: 12px;"><div style="font-size: 12px; font-weight: 600; color: #111827; margin-bottom: 8px;">Sản phẩm nổi bật:</div>{products_html}</div>' if products_html else ''
            
            # Build HTML response
            html = f"""
            <div style="
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                padding: 16px;
                margin: 8px 0;
                background: #ffffff;
                font-family: system-ui, -apple-system, sans-serif;
                max-width: 320px;
                min-width: 320px;
                box-shadow: 0 1px 2px rgba(0,0,0,0.05);
            ">
                <!-- Brand Header -->
                <div style="display: flex; align-items: center; margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #f3f4f6;">
                    <div style="width: 50px; height: 50px; background: #f9fafb; border-radius: 6px; display: flex; align-items: center; justify-content: center; margin-right: 12px; flex-shrink: 0;">
                        {logo_html}
                    </div>
                    <div style="flex: 1; min-width: 0;">
                        <div style="font-size: 16px; font-weight: 700; color: #111827;">{brand_name}</div>
                        <div style="font-size: 12px; color: #6b7280; margin-top: 2px;">Chính hãng</div>
                    </div>
                </div>
                
                <!-- Description -->
                {desc_section}
                
                <!-- Product Count -->
                <div style="margin-bottom: 12px; padding: 10px; background: #f9fafb; border-radius: 4px; text-align: center;">
                    <div style="font-size: 24px; font-weight: 700; color: #111827;">{product_count}</div>
                    <div style="font-size: 11px; color: #6b7280; margin-top: 2px;">sản phẩm</div>
                </div>
                
                <!-- Sample Products -->
                {products_section}
            
            </div>
            """
            
            dispatcher.utter_message(text=html)
            
        except Exception as e:
            print(f"Error in ActionAskBrandInfo: {e}")
            import traceback
            print(traceback.format_exc())
            dispatcher.utter_message(text=f"Xin lỗi, đã có lỗi khi lấy thông tin về {brand_name}.")
        
        return []
