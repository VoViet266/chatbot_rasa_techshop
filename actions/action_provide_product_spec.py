from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from utils.database import DatabaseService
from utils.product_pipelines import build_search_pipeline
from bson import ObjectId
from typing import Dict, Any, List


class ActionProvideProductSpec(Action):
    def name(self) -> str:
        return "action_provide_product_spec"

    # Mapping keywords
    KEYWORD_MAPPING = {
        "pin": ["battery", "mah", "sac", "charging", "capacity"],
        "ram": ["ram", "memory"],
        "bộ nhớ": ["storage", "rom", "capacity", "gb", "memory"],
        "camera": ["camera", "cam", "resolution", "megapixels", "mp"],
        "màn hình": ["screen", "display", "oled", "lcd", "inch", "resolution"],
        "cpu": ["cpu", "processor", "chip", "core", "ghz"],
        "chip": ["cpu", "processor", "chip"],
        "gpu": ["gpu", "graphics", "video"],
        "hệ điều hành": ["os", "android", "ios", "operating", "system"],
        "kích thước": ["size", "dimension", "width", "height", "depth"],
        "trọng lượng": ["weight", "mass", "kg", "gram"],
        "kết nối": ["wifi", "bluetooth", "gps", "nfc", "sim", "cellular", "5g"],
    }

    def format_value(self, value) -> str:
        """Hàm phụ trợ để làm đẹp giá trị (bỏ ngoặc nhọn, format list)"""
        if isinstance(value, bool):
            return "Có" if value else "Không"
        
        if isinstance(value, list):
            # Nếu là list ảnh hoặc list string -> nối lại
            return ", ".join([str(v) for v in value])
            
        if isinstance(value, dict):
            # QUAN TRỌNG: Nếu value là dict (VD: memory: {ram: 8gb, rom: 128gb})
            # Format thành chuỗi đẹp: "Ram: 8gb, Rom: 128gb"
            parts = []
            for k, v in value.items():
                parts.append(f"{k.upper()}: {v}")
            return " | ".join(parts)

        return str(value)

    def find_specs_recursive(self, data: Dict, keywords: List[str]) -> List[str]:
        """Tìm thông số đệ quy và xử lý Dict lồng nhau"""
        found_results = []
        
        # Data có thể là product gốc hoặc variants
        # Ưu tiên tìm trong 'attributes' nếu có, hoặc tìm trực tiếp
        target_data = data.get("attributes", data)
        
        if not isinstance(target_data, dict):
            return []

        # 1. Duyệt qua từng key trong data
        for key, value in target_data.items():
            if not value: 
                continue
                
            key_lower = key.lower()
            
            # TRƯỜNG HỢP 1: Value là Dict (ví dụ 'memory', 'display')
            # Ta cần chui vào trong để tìm xem có keyword (ví dụ 'ram') không
            if isinstance(value, dict):
                # Gọi đệ quy vào trong
                sub_results = self.find_specs_recursive(value, keywords)
                if sub_results:
                    found_results.extend(sub_results)
                
                # Nếu không tìm thấy gì bên trong, nhưng TÊN KEY CỦA DICT CHA khớp keyword
                # (Ví dụ: hỏi 'bộ nhớ', keyword 'memory', mà data chỉ có key 'memory' chứ ko có 'rom')
                elif any(kw in key_lower for kw in keywords):
                    val_str = self.format_value(value)
                    readable_key = key.title()
                    found_results.append(f"{readable_key}: {val_str}")

            # TRƯỜNG HỢP 2: Value là dữ liệu thường (str, int, list)
            else:
                if any(kw in key_lower for kw in keywords):
                    readable_key = key.replace("_", " ").title() # Format key đẹp (screen_size -> Screen Size)
                    val_str = self.format_value(value)
                    found_results.append(f"{readable_key}: {val_str}")

        return found_results

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[str, Any]):

        db = DatabaseService()
        product_name = tracker.get_slot("product_name")
        spec_type = tracker.get_slot("spec_type")

        if not product_name:
            dispatcher.utter_message("Bạn muốn xem thông số của sản phẩm nào?")
            return []
        
        if not spec_type:
            dispatcher.utter_message(f"Bạn muốn xem thông số gì của {product_name}?")
            return []

        # Tìm sản phẩm
        try:
            pipeline = build_search_pipeline(product_name)
            product = next(db.products_collection.aggregate(pipeline), None)
        except Exception:
            product = None

        if not product:
            dispatcher.utter_message(f"Xin lỗi, tôi không tìm thấy sản phẩm {product_name}.")
            return []

        product_display = product.get("name", product_name)
        spec_type_clean = spec_type.lower().strip()

        # Xác định keywords cần tìm
        search_keywords = self.KEYWORD_MAPPING.get(spec_type_clean, [spec_type_clean])
        results = []

        # 1. Tìm trong Product chính
        prod_specs = self.find_specs_recursive(product, search_keywords)
        
        # Lọc trùng lặp (đôi khi đệ quy gây trùng)
        seen = set()
        unique_prod_specs = []
        for s in prod_specs:
            if s not in seen:
                unique_prod_specs.append(s)
                seen.add(s)

        if unique_prod_specs:
            for s in unique_prod_specs:
                # Format HTML cho đẹp
                key_part, val_part = s.split(":", 1) if ":" in s else (s, "")
                results.append(f"<li style='margin-bottom: 5px;'><strong>{key_part}:</strong> {val_part}</li>")

        # 2. Tìm trong Variants (để so sánh nếu các bản khác nhau)
        variant_ids = product.get("variants", [])
        if variant_ids and len(results) == 0: # Chỉ tìm variant nếu product chính ko có info hoặc muốn show thêm
            try:
                # Lấy tối đa 2 variants để mẫu
                obj_ids = [ObjectId(v) if isinstance(v, str) else v for v in variant_ids[:2]]
                variants = list(db.variants_collection.find({"_id": {"$in": obj_ids}}))
                
                for v in variants:
                    v_name = v.get("name", "Bản khác")
                    v_specs = self.find_specs_recursive(v, search_keywords)
                    
                    # Lọc trùng variant specs
                    for s in v_specs:
                        results.append(f"<li style='margin-bottom: 5px;'><strong>{v_name}:</strong> {s.split(':', 1)[-1]}</li>")
            except Exception as e:
                print(f"Error fetching variants: {e}")

        # Trả lời
        if not results:
            dispatcher.utter_message(
                text=f"Tôi không tìm thấy thông tin về **{spec_type}** cho **{product_display}**."
            )
        else:
            html_response = f"""
            <span>Thông số <b>{spec_type}</b> của <b>{product_display}</b>:</span>
            <ul style="list-style-type: disc; padding-left: 20px; margin-top: 5px;">
                {"".join(results)}
            </ul>
            """
            dispatcher.utter_message(text=html_response)

        return [SlotSet("spec_type", spec_type)]


class ActionProvideProductTechnicalSpecs(Action):
    def name(self) -> str:
        return "action_provide_product_technical_specs"

    SPEC_CATEGORIES = {
        "Hiệu năng": ["cpu", "processor", "chip", "ram", "memory", "gpu"],
        "Lưu trữ": ["storage", "rom",  "ssd", "hdd"],
        "Màn hình": ["screen", "display", "resolution", "inch", "oled", "lcd"],
        "Camera": ["camera", "cam", "megapixel", "mp", "lens"],
        "Pin & Sạc": ["battery", "mah", "charging", "charge", "batteryCapacity"],
        "Kết nối": ["wifi", "bluetooth", "nfc", "sim", "5g"],
        "Thiết kế": ["size", "dimension", "weight", "color", "material"],
        "Hệ điều hành": ["os", "android", "ios", "operating"],
    }

    def format_recursive(self, value):
        """Hàm làm phẳng dữ liệu nested dict thành string"""
        if isinstance(value, dict):
            parts = []
            for k, v in value.items():
                # Đệ quy tiếp nếu lồng nhau nhiều cấp
                parts.append(f"{k.upper()} {self.format_recursive(v)}")
            return ", ".join(parts)
        elif isinstance(value, list):
            return ", ".join([str(v) for v in value])
        else:
            return str(value)

    def categorize_specs(self, data: Dict) -> Dict[str, List[tuple]]:
        categorized = {cat: [] for cat in self.SPEC_CATEGORIES.keys()}
        categorized["ℹ️ Thông tin khác"] = []
        
        target_data = data.get("attributes", data)
        
        # Hàm nội bộ để duyệt data phẳng hóa
        def traverse_and_categorize(current_data, prefix=""):
            if not isinstance(current_data, dict):
                return

            for key, value in current_data.items():
                if not value or key.startswith("_") or key == "images": continue
                
                key_lower = key.lower()
                
                # Nếu gặp dict con (vd: memory: {ram:..., rom:...})
                if isinstance(value, dict):
                    # 1. Thử categorize cái dict cha này luôn (nếu tên nó khớp category)
                    matched_category = False
                    for category, keywords in self.SPEC_CATEGORIES.items():
                        if any(kw in key_lower for kw in keywords):
                            # Format toàn bộ dict con thành chuỗi đẹp
                            val_str = self.format_recursive(value)
                            categorized[category].append((key, val_str))
                            matched_category = True
                            break
                    
                    # 2. Nếu dict cha ko khớp category nào đặc biệt, ta chui vào con
                    if not matched_category:
                        traverse_and_categorize(value, prefix=key + " ")
                    continue

                # Xử lý giá trị thường
                val_str = self.format_recursive(value)
                if isinstance(value, bool): val_str = "Có" if value else "Không"

                found = False
                for category, keywords in self.SPEC_CATEGORIES.items():
                    if any(kw in key_lower for kw in keywords):
                        categorized[category].append((prefix + key, val_str))
                        found = True
                        break
                
                if not found and not prefix: # Chỉ đưa vào 'Khác' nếu ở root level
                    categorized["ℹ️ Thông tin khác"].append((key, val_str))

        traverse_and_categorize(target_data)
        return categorized

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[str, Any]):

        db = DatabaseService()
        product_name = tracker.get_slot("product_name")

        if not product_name:
            dispatcher.utter_message("Bạn muốn xem thông số kỹ thuật của sản phẩm nào?")
            return []

        try:
            pipeline = build_search_pipeline(product_name)
            product = next(db.products_collection.aggregate(pipeline), None)
        except Exception:
            product = None

        if not product:
            dispatcher.utter_message(f"Xin lỗi, tôi không tìm thấy sản phẩm {product_name}.")
            return []

        product_display = product.get("name", product_name)
        categorized_specs = self.categorize_specs(product)
        
        html_sections = []
        for category, specs in categorized_specs.items():
            if not specs: continue
            
            items_html = ""
            for key, value in specs:
                # Làm đẹp tên Key (ví dụ: memory ram -> Memory Ram -> Ram)
                display_key = key.replace("_", " ").title()
                
                items_html += f"""
                <tr>
                    <td style="padding: 5px 10px; border-bottom: 1px solid #eee; width: 40%; color: #555;">{display_key}</td>
                    <td style="padding: 5px 10px; border-bottom: 1px solid #eee; font-weight: 500;">{value}</td>
                </tr>
                """
            
            html_sections.append(f"""
            <div style="margin-bottom: 15px;">
                <div style="background-color: #f0f2f5; padding: 5px 10px; border-radius: 5px; font-weight: bold; color: #1a73e8;">
                    {category}
                </div>
                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                    {items_html}
                </table>
            </div>
            """)
        
        full_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 100%;">
            <h3 style="text-align: center; margin-top: 0;">📱 {product_display}</h3>
            {"".join(html_sections)}
        </div>
        """
        
        # Gửi Message text nhưng render HTML
        dispatcher.utter_message(text=full_html)
        return []