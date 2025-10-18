from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from pymongo import MongoClient
from utils.render_product_ui import render_ui
import re

def convert_price_to_number(price_text):
    """Convert price text to integer number in VND
    Examples:
    - "15 triệu" -> 15000000
    - "15 nghìn" -> 15000
    - "15" -> 15
    """
    number = float(re.findall(r'\d+', price_text)[0])
    if 'triệu' in price_text.lower():
        return int(number * 1000000)
    elif 'nghìn' in price_text.lower():
        return int(number * 1000)
    return int(number)

class ActionSuggestProductPrice(Action):
    def name(self):
        return "action_suggest_product_price"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain):
        
        CHEAP_PRICE_THRESHOLD = '5 triệu'  # Ví dụ: 5 triệu
        EXPENSIVE_PRICE_THRESHOLD = '20 triệu' # Ví dụ: 20 triệu
        
        text = tracker.latest_message.get("text", "").lower()
        min_price = tracker.get_slot("min_price")
        max_price = tracker.get_slot("max_price")
        category = tracker.get_slot("category")
        price_qualifier = tracker.get_slot("price_qualifier")

        print('Loại:', price_qualifier)

        if price_qualifier == "cheap" and max_price is None:
            max_price = CHEAP_PRICE_THRESHOLD
        elif price_qualifier == "expensive" and min_price is None:
            min_price = EXPENSIVE_PRICE_THRESHOLD

        client = MongoClient("mongodb+srv://VieDev:durNBv9YO1TvPvtJ@cluster0.h4trl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
        database = client["techshop_db"]

        categories_model = database["categories"]
        category_document = categories_model.find_one({"name": {"$regex": category, "$options": "i"}})
        category_id = category_document["_id"]
        
        products_model = database["products"]
        products_collection = products_model.find({"category": category_id})

        variants_model = database["variants"]

        result = []
        for product in products_collection:
            variants = []
            for variant_id in product['variants']:
                variant = variants_model.find_one({"_id": variant_id})
                variants.append(variant)
            for variant in variants:
                if min_price and not(max_price):
                    if variant['price'] >= convert_price_to_number(min_price):
                        variant['discount'] = product.get('discount', 0)
                        variant['product_id'] = product.get('_id')
                        result.append(variant)
                elif max_price and not(min_price):
                    if variant['price'] <= convert_price_to_number(max_price):
                        variant['discount'] = product.get('discount', 0)
                        variant['product_id'] = product.get('_id')
                        result.append(variant)
                elif min_price and max_price:
                    if convert_price_to_number(min_price) <= variant['price'] <= convert_price_to_number(max_price):
                        variant['discount'] = product.get('discount', 0)
                        variant['product_id'] = product.get('_id')
                        result.append(variant)
        
        # print(render_ui(result))
        # html_result = render_ui(result)
        # dispatcher.utter_message(text=html_result, html=True)
        dispatcher.utter_message(json_message=render_ui(result))
        
        return [SlotSet('min_price', None), SlotSet('max_price', None), SlotSet('price_qualifier', None)]
