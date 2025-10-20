from pymongo import MongoClient
from rasa_sdk.events import SlotSet
from rasa_sdk import Action, Tracker
from utils.render_product_ui import render_ui
from utils.extract_number import extract_number
from rasa_sdk.executor import CollectingDispatcher
from utils.convert_price_to_number import convert_price_to_number

class ActionSuggestProduct(Action):
    def name(self):
        return "action_suggest_product"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain):
        
        CHEAP_PRICE_THRESHOLD = '5 triệu'  # Ví dụ: 5 triệu
        EXPENSIVE_PRICE_THRESHOLD = '20 triệu' # Ví dụ: 20 triệu

        MIN_RAM_THRESHOLD = '8 GB'  # Ví dụ: 5 GB
        MAX_RAM_THRESHOLD = '16 GB' # Ví dụ: 20 GB

        MIN_BATTERY_THRESHOLD = '4000 mAh'
        
        category = tracker.get_slot("category")
        if not(category):
            dispatcher.utter_message(text='Quý khách vui lòng cung cấp thông tin thể loại để hệ thống có thể đưa ra những gợi ý phù hợp nhất với bạn nhé!')
            return []
        
        min_price = tracker.get_slot("min_price")
        max_price = tracker.get_slot("max_price")
        
        min_ram = tracker.get_slot("min_ram")
        max_ram = tracker.get_slot("max_ram")
        
        min_battery = tracker.get_slot("min_battery")
        
        price_qualifier = tracker.get_slot("price_qualifier")
        ram_qualifier = tracker.get_slot("ram_qualifier")
        battery_qualifier = tracker.get_slot("battery_qualifier")

        if price_qualifier == "cheap" and max_price is None:
            max_price = CHEAP_PRICE_THRESHOLD
        elif price_qualifier == "expensive" and min_price is None:
            min_price = EXPENSIVE_PRICE_THRESHOLD

        if ram_qualifier == "low_ram" and max_ram is None:
            max_ram = MIN_RAM_THRESHOLD
        elif ram_qualifier == "high_ram" and min_ram is None:
            min_ram = MAX_RAM_THRESHOLD

        if battery_qualifier == "high_battery":
            min_battery = MIN_BATTERY_THRESHOLD
        
        client = MongoClient("mongodb+srv://VieDev:durNBv9YO1TvPvtJ@cluster0.h4trl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
        database = client["techshop_db"]

        categories_model = database["categories"]
        category_document = categories_model.find_one({"name": {"$regex": category, "$options": "i"}})

        category_id = category_document["_id"]
        
        products_model = database["products"]
        query = {
            "category": category_id
        }

        battery_conditions = []

        if min_battery:
            battery_conditions.append({
                '$gte': [
                    {
                        '$convert': {
                            'input': {
                                '$arrayElemAt': [
                                    { '$split': ['$attributes.batteryCapacity', ' '] },
                                    0
                                ]
                            },
                            'to': 'int',
                            'onError': 0,
                            'onNull': 0
                        }
                    },
                    extract_number(min_battery)
                ]
            })

        if len(battery_conditions) == 1:
            query['$expr'] = battery_conditions[0]
        elif len(battery_conditions) == 2:
            query['$expr'] = { '$and': battery_conditions }

        products_collection = products_model.find(query)
        products_collection = list(products_collection)

        query = {}
        expr_conditions = []
        if min_price:
            expr_conditions.append({ '$gte': ['$price', convert_price_to_number(min_price)] })
        if max_price:
            expr_conditions.append({ '$lte': ['$price', convert_price_to_number(max_price)] })
        
        if min_ram:
            expr_conditions.append({
                '$gte': [
                    { '$toInt': { '$arrayElemAt': [ { '$split': ['$memory.ram', ' '] }, 0 ] } },
                    extract_number(min_ram)
                ]
            })

        if max_ram:
            expr_conditions.append({
                '$lte': [
                    { '$toInt': { '$arrayElemAt': [ { '$split': ['$memory.ram', ' '] }, 0 ] } },
                    extract_number(max_ram)
                ]
            })

        if len(expr_conditions) == 1:
            query['$expr'] = expr_conditions[0]
        elif len(expr_conditions) > 1:
            query['$expr'] = { '$and': expr_conditions }

        variants_model = database["variants"]
        variant_ids_in_category = []

        for product in products_collection:
            for variant_id in product.get("variants", []):
                variant_ids_in_category.append(variant_id)

        query['_id'] = {"$in": variant_ids_in_category}
        variant_collection = variants_model.find(query)
        variant_collection = list(variant_collection)


        for variant in variant_collection:
            product = products_model.find_one({ "variants": variant['_id'] })
            if product:
                variant['discount'] = product.get('discount', 0)
                battery_capacity = product.get('attributes', {}).get('batteryCapacity')
                if battery_capacity:
                    variant['battery'] = battery_capacity
                variant['product_id'] = product.get('_id')

        if not variant_collection:
            dispatcher.utter_message(text="Rất tiếc, không có sản phẩm nào phù hợp với yêu cầu của bạn")
        else:
            dispatcher.utter_message(text=render_ui(variant_collection))
        
        return [SlotSet('min_price', None), SlotSet('max_price', None), SlotSet('min_ram', None), SlotSet('max_ram', None), SlotSet('price_qualifier', None), SlotSet('ram_qualifier', None), SlotSet('battery_qualifier', None), SlotSet('min_battery', None)]
