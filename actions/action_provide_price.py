from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from pymongo import MongoClient

class ActionProvidePrice(Action):
    def name(self):
        return "action_provide_price"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):

        product_name = tracker.get_slot("product")

        if not product_name:
            dispatcher.utter_message(text="Bạn vui lòng cho tôi biết tên sản phẩm nhé.")
            return []

        # Kết nối MongoDB
        client = MongoClient("mongodb+srv://VieDev:durNBv9YO1TvPvtJ@cluster0.h4trl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
        db = client["techshop_db"]
        products_collection = db["products"]
        variants_collection = db["variants"]

        # 1. Tìm product theo tên
        product = products_collection.find_one({"name": {"$regex": product_name, "$options": "i"}})

        if not product:
            dispatcher.utter_message(text=f"Xin lỗi, tôi không tìm thấy thông tin cho sản phẩm {product_name}.")
            return []

        # 2. Lấy danh sách variant IDs từ product
        variant_ids = product.get("variants", [])
        if not variant_ids:
            dispatcher.utter_message(text=f"Sản phẩm {product['name']} chưa có thông tin giá.")
            return []

        # 3. Tìm variants theo _id
        variants = variants_collection.find({"_id": {"$in": variant_ids}})
        variants = list(variants)


        if len(variants) == 0:
            dispatcher.utter_message(text=f"Sản phẩm {product['name']} chưa có thông tin giá.")
        else:
            message = f"""<div style="display: flex; align-items: center; border: 1px solid #e0e0e0; border-radius: 12px; padding: 16px; margin: 8px 0; background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
  <div style="flex-shrink: 0; margin-right: 16px;">
    <img src="{variants[0]["color"][0]["images"][0]}" alt="${product["name"]}" style="width: 120px; height: 120px; object-fit: cover; border-radius: 8px;" />
  </div>
  <div style="flex-grow: 1;">
    <h3 style="margin: 0 0 8px 0; color: #333; font-size: 15px; font-weight: 600;">${product["name"]}</h3>
    <div style="color: #666; font-size: 14px; line-height: 1.5;">
      <div style="margin-bottom: 4px;"><strong>Giá:</strong> {variants[0]["price"]}</div>
      <div style="margin-bottom: 4px;"><strong>Màu:</strong> {variants[0]["color"][0]["colorName"]}</div>
    </div>
  </div>
</div>"""
            # for v in variants:
            #     ram = v.get("ram", "")
            #     storage = v.get("storage", "")
            #     price = v.get("price", "Liên hệ")
            #     message += f"- {ram} / {storage}: {price:,} VND\n"
            dispatcher.utter_message(text=message)

        return []
