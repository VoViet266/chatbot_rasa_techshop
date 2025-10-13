from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from pymongo import MongoClient
from utils.format_currentcy import format_vnd
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

def render_ui(variants):
    result = "<div style='display:flex;flex-direction:column;gap:8px;'><h4>Gợi ý sản phẩm:</h4>"
    for variant in variants:
        result += f"""<div id="product-template" role="group" aria-label="Sản phẩm" 
  style="display:flex;justify-content:flex-start;align-items:flex-start;box-sizing:border-box;
         padding:0;margin:0;gap:8px;max-width:520px;border-radius:6px;font-family:Arial,Helvetica,sans-serif; border: 1px solid #ececec; padding: 8px;">

  <!-- Ảnh sản phẩm -->
  <div dir="ltr" 
    style="display:flex;flex-direction:column;justify-content:flex-start;align-items:center;flex:0 0 auto;
           padding:0;margin:0;">
    <img src="{variant["color"][0]["images"][0]}" alt="[Tên sản phẩm]" 
         style="width:80px;height:70px;object-fit:contain;object-position:center;">
  </div>

  <!-- Nội dung sản phẩm -->
  <div dir="ltr" 
    style="display:flex;flex-direction:column;justify-content:flex-start;flex:1 1 50px;
           padding:0;margin:0;min-width:0;">

    <!-- Tên sản phẩm -->
    <p aria-hidden="false" 
       style="font-size:12px;color:#101519;line-height:1.33;margin:0 0 4px 0;overflow-wrap:break-word;">
      {variant["name"]}
    </p>

    <!-- Giá tiền hiện tại -->
    <p aria-live="polite" 
       style="font-size:14px;color:#dc2626;font-weight:600;white-space:nowrap;text-overflow:ellipsis;
              overflow:hidden;margin:0 0 6px 0;line-height:1.33;">
      {format_vnd(variant["price"])}₫
    </p>

    <!-- Giá gốc và giảm giá -->
    <div aria-hidden="true" 
         style="display:flex;align-items:center;gap:4px;margin-bottom:6px;">
      <span style="font-size:12px;color:#767676;text-decoration:line-through;line-height:1.33;">
        {format_vnd(variant["price"])}
      </span>
      <span style="font-size:12px;color:red;line-height:1.33;">
        [Giảm giá]
      </span>
    </div>

    <!-- Nút hành động -->
    <div role="toolbar" aria-label="Hành động" 
         style="display:flex;gap:4px;margin-top:4px;">
      <button type="button" tabindex="0" role="button"
        style="display:inline-flex;align-items:center;justify-content:center;padding:6px 8px;
               font-size:12px;color:#101519;background:transparent;border:none;cursor:pointer;
               border-radius:4px;user-select:none;">
        Chọn mua
      </button>
      <button type="button" tabindex="0" role="button"
        style="display:inline-flex;align-items:center;justify-content:center;padding:6px 8px;
               font-size:12px;color:#101519;background:transparent;border:none;cursor:pointer;
               border-radius:4px;user-select:none;">
        Xem ưu đãi
      </button>
    </div>
  </div>
</div>"""
    result += "</div>"
    cleaned_result = re.sub(r'\s+', ' ', result).strip()
    return cleaned_result

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
