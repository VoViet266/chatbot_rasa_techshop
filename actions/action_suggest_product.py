from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from pymongo import MongoClient
from utils.format_currentcy import format_vnd
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

class ActionSuggestProduct(Action):
    def name(self):
        return "action_suggest_product"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain):
        
        text = tracker.latest_message.get("text", "").lower()
        category = tracker.get_slot("category")
        entities = tracker.latest_message['entities']

        client = MongoClient("mongodb+srv://VieDev:durNBv9YO1TvPvtJ@cluster0.h4trl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
        db = client["techshop_db"]
        categories_collection = db["categories"]
        products_collection = db["products"]
        variants_collection = db["variants"]
        category_doc = categories_collection.find_one({"name": {"$regex": category, "$options": "i"}})

        max_price = None
        min_price = None


        if "từ" in text and "đến" in text:
            prices = []
            for entity in entities:
                if entity['entity'] == 'max_price':
                    prices.append(entity['value'])
            if len(prices) >= 2:
                min_price = prices[0]
                max_price = prices[1]
        elif "giá rẻ" in text or "giá thấp" in text:
            max_price = "5 triệu"
        else:
            for entity in entities:
                if entity['entity'] == 'max_price' and "trên" in text:
                    min_price = entity['value']
                elif entity['entity'] == 'max_price':
                    max_price = entity['value']

        if category_doc and ("giá" or "triệu" in text):
            category_id = category_doc["_id"]
            products = products_collection.find({"category": category_id})
            variant_ids = [variant_id for product in products for variant_id in product["variants"]]

            result = []
            if "đến" in text and min_price and max_price:
                for variant_id in variant_ids:    
                    variant = variants_collection.find_one({"_id": variant_id})
                    if convert_price_to_number(min_price) <= variant["price"] and variant["price"] <= convert_price_to_number(max_price):
                        result.append(variant)
            elif "trên" in text and min_price:
                for variant_id in variant_ids:    
                    variant = variants_collection.find_one({"_id": variant_id})
                    if variant["price"] >= convert_price_to_number(min_price):
                        result.append(variant)
            elif "dưới" or "giá rẻ" in text and max_price:
                for variant_id in variant_ids:    
                    variant = variants_collection.find_one({"_id": variant_id})
                    if variant["price"] <= convert_price_to_number(max_price):
                        result.append(variant)
            
            elif "đến" in text and min_price and max_price:
                for variant_id in variant_ids:    
                    variant = variants_collection.find_one({"_id": variant_id})
                    if convert_price_to_number(min_price) <= variant["price"] and variant["price"] <= convert_price_to_number(max_price):
                        result.append(variant)

        result = render_ui(result)
        dispatcher.utter_message(text=result, html=True)
        
        return []
