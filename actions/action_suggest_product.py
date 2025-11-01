from pymongo import MongoClient
from rasa_sdk.events import SlotSet
from rasa_sdk import Action, Tracker
from utils.render_product_ui import render_ui
from utils.extract_number import extract_number
from rasa_sdk.executor import CollectingDispatcher
from utils.convert_price_to_number import convert_price_to_number
from typing import Any, Text, Dict, List

# --- CÁC NGƯỠNG SỐ (nên dùng số thay vì string) ---
CHEAP_PRICE_THRESHOLD = 5000000     # 5 triệu
EXPENSIVE_PRICE_THRESHOLD = 20000000 # 20 triệu

MIN_RAM_THRESHOLD = 8               # 8 GB
MAX_RAM_THRESHOLD = 16              # 16 GB

MIN_BATTERY_THRESHOLD = 4000        # 4000 mAh
MIN_STORAGE_THRESHOLD = 128         # 128 GB

class ActionSuggestProduct(Action):
    
    # --- VẤN ĐỀ 3: Khởi tạo kết nối DB 1 LẦN ---
    # Di chuyển kết nối DB ra ngoài hàm run, vào __init__
    def __init__(self):
        self.client = MongoClient("mongodb+srv://VieDev:durNBv9YO1TvPvtJ@cluster0.h4trl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
        self.database = self.client["techshop_db"]
        self.categories_model = self.database["categories"]
        self.products_model = self.database["products"]
        self.variants_model = self.database["variants"]

    def name(self) -> Text:
        return "action_suggest_product"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        category_name = tracker.get_slot("category")
        if not category_name:
            dispatcher.utter_message(text='Quý khách vui lòng cung cấp thông tin thể loại để hệ thống có thể đưa ra những gợi ý phù hợp nhất với bạn nhé!')
            return []
        
        # --- Xử lý Category (Thêm kiểm tra lỗi) ---
        try:
            category_document = self.categories_model.find_one({"name": {"$regex": category_name, "$options": "i"}})
            if not category_document:
                dispatcher.utter_message(text=f"Xin lỗi, tôi không tìm thấy danh mục sản phẩm: {category_name}")
                return []
            category_id = category_document["_id"]
        except Exception as e:
            print(f"Lỗi khi tìm category: {e}")
            dispatcher.utter_message(text="Đã có lỗi xảy ra khi tìm danh mục sản phẩm.")
            return []

        # --- Lấy các slot ---
        min_price = tracker.get_slot("min_price")
        max_price = tracker.get_slot("max_price")
        
        min_ram = tracker.get_slot("min_ram")
        max_ram = tracker.get_slot("max_ram")

        min_storage = tracker.get_slot("min_storage")
        max_storage = tracker.get_slot("max_storage")
        
        min_battery = tracker.get_slot("min_battery")
        
        price_qualifier = tracker.get_slot("price_qualifier")
        ram_qualifier = tracker.get_slot("ram_qualifier")
        battery_qualifier = tracker.get_slot("battery_qualifier")
        # --- LỖI 4: Fix lỗi copy-paste ---
        storage_qualifier = tracker.get_slot("storage_qualifier") 

        # --- Chuyển đổi các slot (text) sang số (number) ---
        # Chúng ta chỉ gọi hàm helper 1 lần khi lấy slot
        min_price_num = convert_price_to_number(min_price) if min_price else None
        max_price_num = convert_price_to_number(max_price) if max_price else None
        min_ram_num = extract_number(min_ram) if min_ram else None
        max_ram_num = extract_number(max_ram) if max_ram else None
        min_storage_num = extract_number(min_storage) if min_storage else None
        max_storage_num = extract_number(max_storage) if max_storage else None
        min_battery_num = extract_number(min_battery) if min_battery else None

        # --- Áp dụng các ngưỡng (threshold) ---
        if price_qualifier == "cheap" and max_price_num is None:
            max_price_num = CHEAP_PRICE_THRESHOLD
        elif price_qualifier == "expensive" and min_price_num is None:
            min_price_num = EXPENSIVE_PRICE_THRESHOLD

        if ram_qualifier == "low_ram" and max_ram_num is None:
            max_ram_num = MIN_RAM_THRESHOLD
        elif ram_qualifier == "high_ram" and min_ram_num is None:
            min_ram_num = MAX_RAM_THRESHOLD

        if battery_qualifier == "high_battery" and min_battery_num is None:
            min_battery_num = MIN_BATTERY_THRESHOLD

        if storage_qualifier == "high_storage" and min_storage_num is None:
            min_storage_num = MIN_STORAGE_THRESHOLD

        # --- VẤN ĐỀ 1 & 2: Xây dựng 1 Pipeline tổng hợp ---
        pipeline = []
        match_conditions = []

        # --- Stage 1: Lọc Product theo Category ---
        pipeline.append({
            '$match': { 'category': category_id }
        })

      
        pipeline.append({
            '$lookup': {
                'from': 'variants',       
                'localField': 'variants',   
                'foreignField': '_id',     
                'as': 'variant_data'    
            }
        })

 
        pipeline.append({ '$unwind': '$variant_data' })

      
        if min_price_num:
            match_conditions.append({ 'variant_data.price': { '$gte': min_price_num } })
        if max_price_num:
            match_conditions.append({ 'variant_data.price': { '$lte': max_price_num } })

  
        if min_ram_num:
            match_conditions.append({
                '$expr': {
                    '$gte': [
                        { '$toInt': { '$arrayElemAt': [ { '$split': ['$variant_data.memory.ram', ' '] }, 0 ] } },
                        min_ram_num
                    ]
                }
            })
        if max_ram_num:
            match_conditions.append({
                '$expr': {
                    '$lte': [
                        { '$toInt': { '$arrayElemAt': [ { '$split': ['$variant_data.memory.ram', ' '] }, 0 ] } },
                        max_ram_num
                    ]
                }
            })

        # Lọc Storage (trên `variant_data.memory.storage`)
        if min_storage_num:
            match_conditions.append({
                '$expr': {
                    '$gte': [
                        { '$toInt': { '$arrayElemAt': [ { '$split': ['$variant_data.memory.storage', ' '] }, 0 ] } },
                        min_storage_num
                    ]
                }
            })
        if max_storage_num:
            match_conditions.append({
                '$expr': {
                    '$lte': [
                        { '$toInt': { '$arrayElemAt': [ { '$split': ['$variant_data.memory.storage', ' '] }, 0 ] } },
                        max_storage_num
                    ]
                }
            })

        
        if min_battery_num:
            match_conditions.append({
                '$expr': {
                    '$gte': [
                        { '$convert': { 'input': { '$arrayElemAt': [ { '$split': ['$attributes.batteryCapacity', ' '] }, 0 ] }, 'to': 'int', 'onError': 0, 'onNull': 0 } },
                        min_battery_num
                    ]
                }
            })

        if match_conditions:
            pipeline.append({
                '$match': { '$and': match_conditions }
            })

      
        pipeline.append({
            '$replaceRoot': {
                'newRoot': {
                    '$mergeObjects': [
                        '$variant_data',
                        { 
                            'discount': '$discount', 
                            'product_id': '$_id',
                            'battery': '$attributes.batteryCapacity'
                        }
                    ]
                }
            }
        })
        
        try:
            results = list(self.products_model.aggregate(pipeline))
            
            if not results:
                dispatcher.utter_message(text="Rất tiếc, không có sản phẩm nào phù hợp với yêu cầu của bạn")
            else:
                dispatcher.utter_message(text=render_ui(results))
        
        except Exception as e:
            print(f"Lỗi khi aggregate: {e}")
            dispatcher.utter_message(text="Đã có lỗi xảy ra trong quá trình tìm kiếm sản phẩm.")
        return [
            SlotSet('min_price', None), SlotSet('max_price', None),
            SlotSet('min_ram', None), SlotSet('max_ram', None),
            SlotSet('min_storage', None), SlotSet('max_storage', None),
            SlotSet('min_battery', None),
            SlotSet('price_qualifier', None), SlotSet('ram_qualifier', None),
            SlotSet('battery_qualifier', None), SlotSet('storage_qualifier', None)
        ]