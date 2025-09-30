from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from pymongo import MongoClient
from bson import ObjectId
import google.generativeai as genai
import json
from utils.format_currentcy import format_vnd

# Cấu hình Gemini
GEMINI_API_KEY = "AIzaSyDoV-Wrx3it_aeTOgJbqb06_jZN8wimM2s"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

class DatabaseService:
    """Service để kết nối và truy vấn MongoDB"""
    
    def __init__(self):
        self.client = MongoClient("mongodb+srv://VieDev:durNBv9YO1TvPvtJ@cluster0.h4trl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
        self.db = self.client["techshop_db"]
        self.products_collection = self.db["products"]
        self.variants_collection = self.db["variants"]
        self.brands_collection = self.db["brands"]
        self.categories_collection = self.db["categories"]

    def get_product_by_name(self, product_name: str) -> Dict[str, Any]:
        """Tìm sản phẩm cụ thể theo tên"""
        try:
            # Tìm sản phẩm theo tên (không phân biệt hoa thường)
            product = self.products_collection.find_one({
                "name": {"$regex": product_name, "$options": "i"}
            })
            
            if not product:
                return {}
            
            # Lấy thông tin brand
            brand = None
            if product.get("brand"):
                brand = self.brands_collection.find_one({"_id": ObjectId(product["brand"])})
            
            # Lấy thông tin category
            category = None
            if product.get("category"):
                category = self.categories_collection.find_one({"_id": ObjectId(product["category"])})
            
            # Lấy variants
            variants = []
            if product.get("variants"):
                variant_object_ids = [ObjectId(vid) for vid in product["variants"]]
                variants = list(self.variants_collection.find({"_id": {"$in": variant_object_ids}}))
            
            return {
                'product': product,
                'brand': brand,
                'category': category,
                'variants': variants
            }
            
        except Exception as e:
            print(f"Lỗi tìm sản phẩm: {e}")
            return {}

    def search_products(self, query_filters: Dict[str, Any], limit: int = 10) -> List[Dict]:
        """Tìm kiếm sản phẩm dựa trên filters"""
        try:
            # Build MongoDB query
            mongo_query = {"isActive": True}  # Chỉ lấy sản phẩm đang active
            
            # Tìm theo tên sản phẩm
            if query_filters.get('product_name'):
                mongo_query["name"] = {
                    "$regex": query_filters['product_name'], 
                    "$options": "i"
                }
            
            # Tìm theo brand
            if query_filters.get('brand'):
                # Tìm brand_id trước
                brand = self.brands_collection.find_one({
                    "name": {"$regex": query_filters['brand'], "$options": "i"}
                })
                if brand:
                    mongo_query["brand"] = str(brand["_id"])
            
            # Lấy danh sách sản phẩm
            products = list(self.products_collection.find(mongo_query).limit(limit))
            
            # Enrich với thông tin brand, category và variants
            enriched_products = []
            for product in products:
                # Lấy thông tin brand
                brand = None
                if product.get("brand"):
                    brand = self.brands_collection.find_one({"_id": ObjectId(product["brand"])})
                
                # Lấy thông tin category
                category = None
                if product.get("category"):
                    category = self.categories_collection.find_one({"_id": ObjectId(product["category"])})
                
                # Lấy variants
                variants = []
                if product.get("variants"):
                    variant_object_ids = [ObjectId(vid) for vid in product["variants"]]
                    variants = list(self.variants_collection.find({"_id": {"$in": variant_object_ids}}))
                
                # Filter theo giá nếu có
                if query_filters.get('price_min') or query_filters.get('price_max'):
                    filtered_variants = []
                    for variant in variants:
                        price = variant.get('price', 0)
                        price_min = query_filters.get('price_min', 0)
                        price_max = query_filters.get('price_max', float('inf'))
                        if price_min <= price <= price_max:
                            filtered_variants.append(variant)
                    variants = filtered_variants
                
                # Chỉ thêm product nếu có variants phù hợp hoặc không filter theo giá
                if variants or not (query_filters.get('price_min') or query_filters.get('price_max')):
                    enriched_products.append({
                        'product': product,
                        'brand': brand,
                        'category': category,
                        'variants': variants
                    })
            
            return enriched_products
            
        except Exception as e:
            print(f"❌ Lỗi tìm kiếm: {e}")
            return []

    def get_popular_products(self, limit: int = 5) -> List[Dict]:
        """Lấy sản phẩm phổ biến dựa trên viewCount và soldCount"""
        try:
            # Sort theo viewCount và soldCount giảm dần
            products = list(self.products_collection.find(
                {"isActive": True}
            ).sort([
                ("viewCount", -1), 
                ("soldCount", -1)
            ]).limit(limit))
            
            enriched_products = []
            for product in products:
                # Lấy thông tin brand
                brand = None
                if product.get("brand"):
                    brand = self.brands_collection.find_one({"_id": ObjectId(product["brand"])})
                
                # Lấy thông tin category
                category = None
                if product.get("category"):
                    category = self.categories_collection.find_one({"_id": ObjectId(product["category"])})
                
                # Lấy variants
                variants = []
                if product.get("variants"):
                    variant_object_ids = [ObjectId(vid) for vid in product["variants"]]
                    variants = list(self.variants_collection.find({"_id": {"$in": variant_object_ids}}))
                
                enriched_products.append({
                    'product': product,
                    'brand': brand,
                    'category': category,
                    'variants': variants
                })
            
            return enriched_products
            
        except Exception as e:
            print(f"❌ Lỗi lấy sản phẩm phổ biến: {e}")
            return []


class ActionProvideProductInfoByGemini(Action):
    """Action tư vấn sản phẩm sử dụng Gemini với dữ liệu từ MongoDB"""
    
    def name(self):
        return "action_search_product"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):
        
        try:
            # Lấy thông tin từ Rasa
            entities = tracker.latest_message.get('entities', [])
            intent = tracker.latest_message.get('intent', {}).get('name')
            user_message = tracker.latest_message.get('text', '')
            product_slot = tracker.get_slot("product")
            
           
            query_filters = self._parse_search_request(entities, user_message, product_slot)
            print(f"🔍 Yêu cầu tìm kiếm: {query_filters}")
            print(f"🔍 Intent: {intent}, Entities: {entities}, User message: {user_message}, Product slot: {product_slot}, UserMessage: {user_message}")
      
            db_service = DatabaseService()
            
           
            products_data = []
            if product_slot:
                # Tìm sản phẩm cụ thể
                product_data = db_service.get_product_by_name(product_slot)
                if product_data:
                    products_data = [product_data]
            
            # Nếu không tìm thấy sản phẩm cụ thể, tìm theo filters
            if not products_data and query_filters:
                products_data = db_service.search_products(query_filters)
            
            # Nếu vẫn không có kết quả, lấy sản phẩm phổ biến
            if not products_data:
                products_data = db_service.get_popular_products()
            
            if not products_data:
                dispatcher.utter_message(text="Xin lỗi, tôi không tìm thấy sản phẩm phù hợp với yêu cầu của bạn. Vui lòng thử lại với từ khóa khác.")
                return []
          
            # Chuẩn bị dữ liệu cho Gemini
            structured_data = self._prepare_data_for_gemini(products_data, query_filters, user_message)
            
            # Gọi Gemini để tạo response
            gemini_response = self._get_gemini_response(structured_data, user_message, intent)
            
            # Gửi response
            dispatcher.utter_message(text=gemini_response)
            
        except Exception as e:
            print(f"❌ Lỗi trong action: {e}")
            dispatcher.utter_message(text="Xin lỗi, tôi đang gặp sự cố kỹ thuật. Vui lòng thử lại sau.")
        
        return []

    def _parse_search_request(self, entities: List[Dict], user_message: str, product_slot: str) -> Dict[str, Any]:
        """Parse yêu cầu tìm kiếm từ entities"""
        filters = {}
        
        if product_slot:
            filters['product_name'] = product_slot
        
        for entity in entities:
            entity_type = entity.get('entity')
            entity_value = entity.get('value', '').lower()
            
            if entity_type == 'product_name':
                filters['product_name'] = entity_value
            elif entity_type == 'brand':
                filters['brand'] = entity_value
            elif entity_type == 'price_range':
                price_info = self._parse_price_range(entity_value, user_message)
                if price_info:
                    filters.update(price_info)
        
        return filters
    
    def _parse_price_range(self, price_text: str, full_message: str) -> Dict[str, int]:
        """Parse giá từ text"""
        import re
        
        price_ranges = {
            'giá rẻ': {'min': 0, 'max': 5000000},
            'giá tốt': {'min': 0, 'max': 8000000},
            'tầm trung': {'min': 5000000, 'max': 15000000},
            'cao cấp': {'min': 15000000, 'max': 50000000}
        }
        
        # Kiểm tra predefined ranges
        for range_text, range_values in price_ranges.items():
            if range_text in price_text.lower():
                return {
                    'price_min': range_values['min'],
                    'price_max': range_values['max']
                }
        
        # Parse số cụ thể
        numbers = re.findall(r'(\d+(?:\.\d+)?)\s*(triệu|tr|k)', price_text + ' ' + full_message.lower())
        if numbers:
            parsed_prices = []
            for num, unit in numbers:
                value = float(num)
                if unit in ['triệu', 'tr']:
                    parsed_prices.append(int(value * 1000000))
                elif unit == 'k':
                    parsed_prices.append(int(value * 1000))
            
            if parsed_prices:
                return {'price_max': max(parsed_prices)}
        
        return {}
    
    def _prepare_data_for_gemini(self, products_data: List[Dict], filters: Dict, user_message: str) -> Dict:
        """Chuẩn bị dữ liệu structured cho Gemini"""
        products_summary = []
        
        for item in products_data[:5]:  # Limit 5 sản phẩm
            product = item['product']
            brand = item.get('brand', {})
            category = item.get('category', {})
            variants = item.get('variants', [])
            
            # Lấy variant có giá thấp nhất và cao nhất
            prices = [v.get('price', 0) for v in variants if v.get('price')]
            min_price = min(prices) if prices else 0
            max_price = max(prices) if prices else 0
            
            # Lấy thông tin RAM/Storage từ variants
            memory_options = []
            colors = []
            images = []
            
            for variant in variants:
                # Lấy thông tin memory
                memory = variant.get('memory', {})
                if memory:
                    ram = memory.get('ram', 'N/A')
                    storage = memory.get('storage', 'N/A')
                    memory_options.append(f"{ram}/{storage}")
                
                # Lấy thông tin màu sắc và hình ảnh
                color_list = variant.get('color', [])
                for color_item in color_list:
                    if color_item.get('colorName'):
                        colors.append(color_item['colorName'])
                    if color_item.get('images'):
                        images.extend(color_item['images'])
            
            product_summary = {
                'name': product.get('name', ''),
                'brand': brand.get('name', 'Không rõ') if brand else 'Không rõ',
                'category': category.get('name', 'Không rõ') if category else 'Không rõ',
                'description': product.get('description', 'Chưa có mô tả'),
                'discount': product.get('discount', 0),
                'price_min': min_price,
                'price_max': max_price,
                'price_range': f"{format_vnd(min_price)} - {format_vnd(max_price)}" if min_price != max_price and max_price > 0 else format_vnd(min_price) if min_price > 0 else "Liên hệ",
                'memory_options': list(set([m for m in memory_options if m != 'N/A/N/A'])),
                'colors': list(set([c for c in colors if c])),
                'variant_count': len(variants),
                'image_url': images[0] if images else '',
                'view_count': product.get('viewCount', 0),
                'sold_count': product.get('soldCount', 0),
                'average_rating': product.get('averageRating', 0),
                'review_count': product.get('reviewCount', 0)
            }
            products_summary.append(product_summary)
        
        return {
            'products': products_summary,
            'filters': filters,
            'user_message': user_message,
            'total_found': len(products_data)
        }
    
    def _get_gemini_response(self, data: Dict, user_message: str, intent: str) -> str:
        """Gọi Gemini để tạo response"""
        try:
            products = data['products']
            
            prompt = f"""
Bạn là chuyên gia tư vấn công nghệ tại Việt Nam. Khách hàng vừa hỏi: "{user_message}"

THÔNG TIN SẢN PHẨM TỪ DATABASE:
{json.dumps(products, ensure_ascii=False, indent=2)}

YÊU CẦU:
1. Phân tích yêu cầu của khách hàng
2. Giới thiệu {len(products)} sản phẩm phù hợp nhất
3. Đưa ra so sánh và gợi ý cụ thể dựa trên view_count, sold_count, rating

FORMAT TRẢ LỜI (HTML):
- Sử dụng HTML tags: <h2>, <h3>, <div>, <span>, <img>, <strong>
- Hiển thị thông tin: tên, thương hiệu, giá, giảm giá, RAM/Storage, màu sắc, lượt xem, đã bán
- Thêm hình ảnh sản phẩm
- Kết thúc bằng câu hỏi follow-up

VÍ DỤ FORMAT:
<h2>📱 GỢI Ý SẢN PHẨM PHỪ HỢP</h2>

<div class="product-item" style="border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 8px;">
  <div style="display: flex; align-items: center;">
    <img src="[IMAGE_URL]" alt="[PRODUCT_NAME]" style="width: 80px; height: 80px; margin-right: 15px; border-radius: 8px; object-fit: cover;">
    <div>
      <h3 style="margin: 0 0 8px 0; color: #333;">[PRODUCT_NAME]</h3>
      <div style="color: #666; font-size: 14px;">
        <div><strong>Thương hiệu:</strong> [BRAND]</div>
        <div><strong>Danh mục:</strong> [CATEGORY]</div>
        <div><strong>Giá:</strong> <span style="color: #e74c3c; font-weight: bold;">[PRICE]</span> <span style="color: #27ae60;">(-[DISCOUNT]%)</span></div>
        <div><strong>Cấu hình:</strong> [RAM/STORAGE_OPTIONS]</div>
        <div><strong>Màu sắc:</strong> [COLORS]</div>
        <div><strong>Thống kê:</strong> [VIEW_COUNT] lượt xem • [SOLD_COUNT] đã bán • [RATING]⭐ ([REVIEW_COUNT] đánh giá)</div>
      </div>
    </div>
  </div>
</div>

LƯU Ý:
- Sử dụng emoji phù hợp
- Giá cả phải chính xác từ database
- Không tự tạo thông số kỹ thuật
- Trả lời bằng tiếng Việt thân thiện
- Ưu tiên sản phẩm có view_count và sold_count cao
"""
            
            response = model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            print(f"❌ Lỗi Gemini: {e}")
            return self._fallback_response(data)
    
    def _fallback_response(self, data: Dict) -> str:
        """Response dự phòng khi Gemini lỗi"""
        products = data['products']
        
        if not products:
            return "Xin lỗi, không tìm thấy sản phẩm phù hợp."
        
        html_response = "<h2>📱 SẢN PHẨM ĐƯỢC TÌM THẤY</h2>"
        
        for product in products[:3]:
            html_response += f"""
            <div style="border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 8px;">
                <div style="display: flex; align-items: center;">
                    <img src="{product['image_url']}" alt="{product['name']}" style="width: 80px; height: 80px; margin-right: 15px; border-radius: 8px; object-fit: cover;">
                    <div>
                        <h3 style="margin: 0 0 8px 0; color: #333;">{product['name']}</h3>
                        <div style="color: #666; font-size: 14px;">
                            <div><strong>Thương hiệu:</strong> {product['brand']}</div>
                            <div><strong>Danh mục:</strong> {product['category']}</div>
                            <div><strong>Giá:</strong> <span style="color: #e74c3c; font-weight: bold;">{product['price_range']}</span></div>
                            <div><strong>Giảm giá:</strong> <span style="color: #27ae60;">{product['discount']}%</span></div>
                            <div><strong>Thống kê:</strong> {product['view_count']} lượt xem • {product['sold_count']} đã bán</div>
                        </div>
                    </div>
                </div>
            </div>
            """
        
        html_response += "<p>Bạn có muốn xem chi tiết sản phẩm nào không?</p>"
        return html_response