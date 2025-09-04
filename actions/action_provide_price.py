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
        product = products_collection.find_one({
    "name": {"$regex": f"^{product_name}$", "$options": "i"}
})
        # product = products_collection.find_one({"name": {"$regex": product_name, "$options": "i"}})

        print("Product name:", product_name)

        if not product:
            dispatcher.utter_message(text=f"Xin lỗi, tôi không tìm thấy thông tin cho sản phẩm {product_name}.")
            return []

        # 2. Lấy danh sách variants theo product_id
        product_id = product["_id"]
        variants = variants_collection.find({"product_id": str(product_id)})
        print("Variants:", list(variants))

        # 3. Ghép dữ liệu lại
        variants = list(variants)
        if len(variants) == 0:
            dispatcher.utter_message(text=f"Sản phẩm {product['name']} chưa có thông tin giá.")
        else:
            message = f"Thông tin giá cho {product['name']}:\n"
            for v in variants:
                ram = v.get("ram", "")
                storage = v.get("storage", "")
                price = v.get("price", "Liên hệ")
                message += f"- {ram} / {storage}: {price:,} VND\n"
            dispatcher.utter_message(text=message)

        return []
