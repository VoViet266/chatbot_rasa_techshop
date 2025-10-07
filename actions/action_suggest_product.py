from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from pymongo import MongoClient
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
        category_doc = categories_collection.find_one({"name": {"$regex": category, "$options": "i"}})

        if category_doc:
            category_id = category_doc["_id"]
            products = products_collection.find({"category_id": category_id})
            product_ids = [product["_id"] for product in products]

        print('Category doc:', category_doc)
        
        # Xử lý entities và từ khóa "trên"/"dưới"
        max_price = None
        min_price = None
    
        # Kiểm tra nếu là khoảng giá (từ X đến Y)
        if "từ" in text and "đến" in text:
            prices = []
            for entity in entities:
                if entity['entity'] == 'max_price':
                    prices.append(entity['value'])
            if len(prices) >= 2:
                min_price = prices[0]  # Giá đầu tiên là min
                max_price = prices[1]  # Giá thứ hai là max
        else:
            # Xử lý các trường hợp trên/dưới
            for entity in entities:
                if entity['entity'] == 'max_price' and "trên" in text:
                    min_price = entity['value']
                elif entity['entity'] == 'max_price':
                    max_price = entity['value']
        
        print('Category:', category)
        print('Max price:', convert_price_to_number(max_price) if max_price else None)
        print('Min price:', convert_price_to_number(min_price) if min_price else None)

        # if "dưới" in text and max_price:
        #     print("Max price:", max_price)
        # elif "trên" in text and min_price:
        #     print("Min price:", min_price)
        # elif "đến" in text and min_price and max_price:
        #     print("Min price:", min_price, "Max price:", max_price)

        # 👉 Sau đó truy vấn database hoặc gọi API gợi ý sản phẩm
        # if max_price and not min_price:
        #     dispatcher.utter_message(text=f"Gợi ý các mẫu laptop giá dưới {max_price} triệu...")
        # elif min_price and not max_price:
        #     dispatcher.utter_message(text=f"Gợi ý các mẫu laptop giá trên {min_price} triệu...")
        # elif min_price and max_price:
        #     dispatcher.utter_message(text=f"Gợi ý các mẫu laptop giá từ {min_price} đến {max_price} triệu...")
        # else:
        #     dispatcher.utter_message(text="Bạn muốn tầm giá khoảng bao nhiêu vậy?")
        dispatcher.utter_message(text="Bạn muốn tầm giá khoảng bao nhiêu vậy?")
        
        return []
