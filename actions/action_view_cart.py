from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from bson import ObjectId
from utils.render_product_ui import render_product_card
from utils.database import DatabaseService


class ActionViewCart(Action):
    def name(self) -> str:
        return "action_view_cart"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        # Lấy user_id
        user_id = tracker.sender_id

        # 1. Kiểm tra đăng nhập
        if not user_id or not ObjectId.is_valid(user_id):
            dispatcher.utter_message(
                text="Quý khách vui lòng đăng nhập để sử dụng dịch vụ."
            )
            return []

        db_service = DatabaseService()
        cart = db_service.carts_collection.find_one({"user": ObjectId(user_id)})

        # Nếu không có giỏ hàng hoặc bị xóa
        if not cart or cart.get("isDeleted", False):
            dispatcher.utter_message(text="Giỏ hàng của bạn hiện đang trống.")
            return []

        items = cart.get("items", [])
        if not items:
            dispatcher.utter_message(text="Giỏ hàng của bạn hiện đang trống.")
            return []

        result = f"<p>Giỏ hàng của bạn có {len(items)} sản phẩm</p>"
        for item in items:
            product = db_service.products_collection.find_one({"_id": item["product"]})
            brand = db_service.brands_collection.find_one({"_id": product["brand"]})
            category = db_service.categories_collection.find_one(
                {"_id": product["category"]}
            )
            if brand:
                product["brand"] = brand["name"]

            if category:
                product["category"] = category["name"]

            variant = list(
                db_service.variants_collection.find({"_id": item["variant"]})
            )
            result += render_product_card(product=product, variants=variant)
        dispatcher.utter_message(text=result)
        return []
