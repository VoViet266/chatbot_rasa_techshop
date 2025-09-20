from rasa_sdk import Action, Tracker
from bson import ObjectId
from rasa_sdk.executor import CollectingDispatcher
from pymongo import MongoClient

class ActionProvideOrderInfo(Action):
    def name(self):
        return "action_provide_order_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):
        
        user_id = tracker.sender_id


        # Kết nối MongoDB
        client = MongoClient("mongodb+srv://VieDev:durNBv9YO1TvPvtJ@cluster0.h4trl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
        db = client["techshop_db"]
        orders_collections = db["orders"]
        products_collections = db["products"]
        orders_info = list(orders_collections.find({"user": ObjectId(user_id)}))

        if(not user_id):
            dispatcher.utter_message(text=f"Xin lỗi! Bạn cần phải đăng nhập để xem được thông tin đơn hàng của mình.")
        
        if(len(orders_info) == 0):
            dispatcher.utter_message(text="Bạn chưa có đơn hàng nào, hãy mua hàng và trải nghiệm dịch vụ của hệ thống nhé!")
        else:
            message = f"""<p class="text-base">Aaaaa, tìm thấy rồi, ní có mua hàng nè</p>"""
            message += """<div class="flex flex-col gap-8">"""
            for order in orders_info:  
                for i in order["items"]:
                    product = products_collections.find_one({ "_id": ObjectId(i["product"]) })
                    if(product):
                        print("Có sản phẩm nè", product)
                        message += f"""<div class="border border-gray-300 rounded-lg shadow-xs p-10">
                        <span class="block"><strong>Tên sản phẩm:</strong> {product["name"]}</span>
                        <span class="block"><strong>Số lượng:</strong> {i["quantity"]}</span>
                        <span class="block"><strong>Đơn giá:</strong> {i["price"]}</span>
                        <span class="block"><strong>Tổng tiền:</strong> {order["totalPrice"]}</span>
                        </div>"""
                    else:
                        print("Không tìm thấy product với id:", i["product"])
        dispatcher.utter_message(text=message)
        return []
