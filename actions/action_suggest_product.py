from rasa_sdk.events import SlotSet
from rasa_sdk import Action, Tracker
from utils.database import DatabaseService
from utils.render_product_ui import render_variants_list 
from utils.extract_number import extract_number
from rasa_sdk.executor import CollectingDispatcher
from utils.convert_price_to_number import convert_price_to_number
from typing import Any, Text, Dict, List

CHEAP_PRICE_THRESHOLD = 10000000
EXPENSIVE_PRICE_THRESHOLD = 20000000 
MIN_RAM_THRESHOLD = 8 
MAX_RAM_THRESHOLD = 16 
MIN_BATTERY_THRESHOLD = 4000 
MIN_STORAGE_THRESHOLD = 128 

class ActionSuggestProduct(Action):
    
    def name(self) -> Text:
        return "action_suggest_product"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        db = DatabaseService()
        
        category_name = tracker.get_slot("category")
        brand_name = tracker.get_slot("brand")
        
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
        storage_qualifier = tracker.get_slot("storage_qualifier") 

        # Process Numeric Values
        min_price_num = convert_price_to_number(min_price) if min_price else None
        max_price_num = convert_price_to_number(max_price) if max_price else None
        min_ram_num = extract_number(min_ram) if min_ram else None
        max_ram_num = extract_number(max_ram) if max_ram else None
        min_storage_num = extract_number(min_storage) if min_storage else None
        max_storage_num = extract_number(max_storage) if max_storage else None
        min_battery_num = extract_number(min_battery) if min_battery else None

        # Apply Qualifiers (Only when explicit values are NOT provided)
        # For "cheap": only set max if user didn't specify any price
        if price_qualifier == "cheap" and min_price_num is None and max_price_num is None:
            max_price_num = CHEAP_PRICE_THRESHOLD
        # For "expensive": only set min if user didn't specify any price  
        elif price_qualifier == "expensive" and min_price_num is None and max_price_num is None:
            min_price_num = EXPENSIVE_PRICE_THRESHOLD
            
        if ram_qualifier == "low_ram" and max_ram_num is None:
            max_ram_num = MIN_RAM_THRESHOLD
        elif ram_qualifier == "high_ram" and min_ram_num is None:
            min_ram_num = MAX_RAM_THRESHOLD
            
        if battery_qualifier == "high_battery" and min_battery_num is None:
            min_battery_num = MIN_BATTERY_THRESHOLD
            
        if storage_qualifier == "high_storage" and min_storage_num is None:
            min_storage_num = MIN_STORAGE_THRESHOLD

        # Build Pipeline
        pipeline = []
        match_product_stage = {}

        # Resolve Category
        if category_name:
            try:
                category_document = db.categories_collection.find_one({"name": {"$regex": category_name, "$options": "i"}})
                if category_document:
                    match_product_stage['category'] = category_document["_id"]
            except Exception as e:
                print(f"Error finding category: {e}")

        # Resolve Brand
        if brand_name:
            try:
                brand_document = db.brands_collection.find_one({"name": {"$regex": brand_name, "$options": "i"}})
                if brand_document:
                    match_product_stage['brand'] = brand_document["_id"]
            except Exception as e:
                print(f"Error finding brand: {e}")

        # If no category/brand and no other filters, ask for more info
        if not match_product_stage and not (min_price_num or max_price_num or min_ram_num or max_ram_num or min_storage_num or max_storage_num or min_battery_num):
             dispatcher.utter_message(text='Quý khách vui lòng cung cấp thêm thông tin (loại sản phẩm, thương hiệu, hoặc mức giá) để hệ thống có thể đưa ra những gợi ý phù hợp nhất!')
             return []

        if match_product_stage:
            pipeline.append({'$match': match_product_stage})

        # Lookup Variants
        pipeline.append({
            '$lookup': {
                'from': 'variants', 'localField': 'variants', 'foreignField': '_id', 'as': 'variant_data'
            }
        })
        pipeline.append({ '$unwind': '$variant_data' })

        # Variant Filters
        match_variant_conditions = []
        
        if min_price_num:
            match_variant_conditions.append({ 'variant_data.price': { '$gte': min_price_num } })
        if max_price_num:
            match_variant_conditions.append({ 'variant_data.price': { '$lte': max_price_num } })
            
        if min_ram_num:
            match_variant_conditions.append({
                '$expr': {
                    '$gte': [
                        { '$toInt': { '$arrayElemAt': [ { '$split': ['$variant_data.memory.ram', ' '] }, 0 ] } },
                        min_ram_num
                    ]
                }
            })
        if max_ram_num:
            match_variant_conditions.append({
                '$expr': {
                    '$lte': [
                        { '$toInt': { '$arrayElemAt': [ { '$split': ['$variant_data.memory.ram', ' '] }, 0 ] } },
                        max_ram_num
                    ]
                }
            })
        if min_storage_num:
            match_variant_conditions.append({
                '$expr': {
                    '$gte': [
                        { '$toInt': { '$arrayElemAt': [ { '$split': ['$variant_data.memory.storage', ' '] }, 0 ] } },
                        min_storage_num
                    ]
                }
            })
        if max_storage_num:
            match_variant_conditions.append({
                '$expr': {
                    '$lte': [
                        { '$toInt': { '$arrayElemAt': [ { '$split': ['$variant_data.memory.storage', ' '] }, 0 ] } },
                        max_storage_num
                    ]
                }
            })
        if min_battery_num:
            match_variant_conditions.append({
                '$expr': {
                    '$gte': [
                        { '$convert': { 'input': { '$arrayElemAt': [ { '$split': ['$attributes.batteryCapacity', ' '] }, 0 ] }, 'to': 'int', 'onError': 0, 'onNull': 0 } },
                        min_battery_num
                    ]
                }
            })

        if match_variant_conditions:
            pipeline.append({'$match': { '$and': match_variant_conditions }})

        # Sorting - Based on qualifiers or default
        sort_stage = {}
        if price_qualifier == "cheap":
            sort_stage['variant_data.price'] = 1  # Ascending (cheapest first)
        elif price_qualifier == "expensive":
            sort_stage['variant_data.price'] = -1  # Descending (most expensive first)
        
        if not sort_stage:
             # Default sort: Price ascending (cheapest first)
             sort_stage['variant_data.price'] = 1
             
        pipeline.append({'$sort': sort_stage})
        
        # Limit results
        pipeline.append({'$limit': 10})

        # Format Output
        pipeline.append({
            '$replaceRoot': {
                'newRoot': {
                    '$mergeObjects': [
                        '$variant_data',
                        { 
                            'discount': '$discount', 
                            'product_id': '$_id',
                            'battery': '$attributes.batteryCapacity',
                            'name': '$name'
                        }
                    ]
                }
            }
        })

        # Execute
        try:
            results = list(db.products_collection.aggregate(pipeline))
            
            if not results:
                dispatcher.utter_message(text="Rất tiếc, không có sản phẩm nào phù hợp với yêu cầu của bạn.")
            else:
                dispatcher.utter_message(text=render_variants_list(results), html=True)
        except Exception as e:
            print(f"Lỗi khi aggregate: {e}")
            dispatcher.utter_message(text="Đã có lỗi xảy ra trong quá trình tìm kiếm sản phẩm.")

        return [
            SlotSet('min_price', None), SlotSet('max_price', None),
            SlotSet('min_ram', None), SlotSet('max_ram', None),
            SlotSet('min_storage', None), SlotSet('max_storage', None),
            SlotSet('min_battery', None),
            SlotSet('price_qualifier', None), SlotSet('ram_qualifier', None),
            SlotSet('battery_qualifier', None), SlotSet('storage_qualifier', None),
            SlotSet('brand', None), SlotSet('category', None)
        ]