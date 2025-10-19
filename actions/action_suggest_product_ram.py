from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from pymongo import MongoClient
from utils.extract_number import extract_number
from utils.render_product_ui import render_ui

class ActionSuggestProductRam(Action):
    def name(self):
        return "action_suggest_product_ram"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain):
        
        MIN_RAM_THRESHOLD = '8 GB'  # Ví dụ: 5 GB
        MAX_RAM_THRESHOLD = '16 GB' # Ví dụ: 20 GB
        
        text = tracker.latest_message.get("text", "").lower()
        min_ram = tracker.get_slot("min_ram")
        max_ram = tracker.get_slot("max_ram")
        category = tracker.get_slot("category")
        ram_qualifier = tracker.get_slot("ram_qualifier")


        if ram_qualifier == "low_ram" and max_ram is None:
            max_ram = MIN_RAM_THRESHOLD
        elif ram_qualifier == "high_ram" and min_ram is None:
            min_ram = MAX_RAM_THRESHOLD

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
                if min_ram and not(max_ram):
                    if extract_number(variant['memory']['ram']) >= extract_number(min_ram):
                        variant['discount'] = product.get('discount', 0)
                        variant['product_id'] = product.get('_id')
                        result.append(variant)
                elif max_ram and not(min_ram):
                    if extract_number(variant['memory']['ram']) <= extract_number(max_ram):
                        variant['discount'] = product.get('discount', 0)
                        variant['product_id'] = product.get('_id')
                        result.append(variant)
                elif min_ram and max_ram:
                    if extract_number(min_ram) <= extract_number(variant['memory']['ram']) <= extract_number(max_ram):
                        variant['discount'] = product.get('discount', 0)
                        variant['product_id'] = product.get('_id')
                        result.append(variant)
        
        dispatcher.utter_message(json_message=render_ui(result))
        
        return [SlotSet('min_ram', None), SlotSet('max_ram', None), SlotSet('ram_qualifier', None)]
