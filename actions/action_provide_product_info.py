from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from pymongo import MongoClient

class ActionProvideProductInfo(Action):
    def name(self):
        return "action_provide_product_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):

        product_name = tracker.get_slot("product")

        print("Product name slot value:", product_name)

        if not product_name:
            dispatcher.utter_message(text="Bạn vui lòng cho tôi biết tên sản phẩm nhé.")
            return []

        # Kết nối MongoDB
        client = MongoClient("mongodb+srv://VieDev:durNBv9YO1TvPvtJ@cluster0.h4trl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
        db = client["techshop_db"]
        products_collection = db["products"]
        variants_collection = db["variants"]
        brands_collection = db["brands"]

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
        brand = brands_collection.find_one({"_id": product["brand"]})
        variants = list(variants)


        if len(variants) == 0:
            dispatcher.utter_message(text=f"Sản phẩm {product['name']} chưa có thông tin giá.")
        else:
          if(product["description"]):
            description = product["description"]
          else:
            description = "Chưa có mô tả"
          message = f"""
          <h2 class="text-lg py-0">{product["name"]}</h2
          <span class="block">Thương hiệu: {brand["name"]}</span>
          <span class="block">Giảm giá: {product["discount"]}%</span>
          <span class="block">Lượt xem: {product["viewCount"]}</span>
          <span class="block">Lượt bán: {product["soldCount"]}</span>
          <p class="block text-justify line-clamp-3">Mô tả: {description}</p>
          <span class="block mb-10">Có tổng cộng {len(variants)} biến thể cho sản phẩm này:</span>
          """
          for v in variants:
            message += f"""<div class="flex items-center border border-gray-300 rounded-lg p-16 my-8 bg-white shadow-md">
            <div class="shrink-0 mr-16">
              <img src="{v["color"][0]["images"][0]}" alt="{product["name"]}" class="w-80 h-80" />
            </div>
            <div class="grow-1">
              <h3 style="margin: 0 0 8px 0; color: #333; font-size: 15px; font-weight: 600;">{product["name"]}</h3>
              <div style="color: #666; font-size: 14px; line-height: 1.5;">
                <div style="margin-bottom: 4px;"><strong>Giá:</strong> {variants[0]["price"]}</div>
                <div style="margin-bottom: 4px;"><strong>Màu:</strong>
              """
            for c in v["color"]:
                message += f"""{c["colorName"]}, """

            message += f"""</div>
            <span class="block mb-4"><strong>RAM:</strong> {v["memory"]["ram"]}</span>
            <span class="block mb-4"><strong>Bộ nhớ trong:</strong> {v["memory"]["storage"]}</span>
            </div>
            </div>
          </div>
            """

            
        dispatcher.utter_message(text=message)

        return []
