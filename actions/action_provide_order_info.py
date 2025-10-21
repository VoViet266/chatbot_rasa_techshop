from rasa_sdk import Action, Tracker
from bson import ObjectId
from bson.errors import InvalidId
from rasa_sdk.executor import CollectingDispatcher
from pymongo import MongoClient
from typing import Any, Text, Dict, List

class ActionProvideOrderInfo(Action):
    def name(self) -> Text:
        return "action_provide_order_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        user_id = tracker.sender_id
        # Lấy order_id từ slot
        order_id_from_slot = tracker.get_slot("order_id")

        # Kiểm tra user_id (giả định sender_id là id trong DB)
        if not user_id:
            dispatcher.utter_message(text="Xin lỗi! Bạn cần phải đăng nhập để xem được thông tin đơn hàng của mình.")
            return []

        try:
            # Chuyển đổi user_id sang ObjectId
            user_object_id = ObjectId(user_id)
        except InvalidId:
            dispatcher.utter_message(text=f"ID người dùng không hợp lệ: {user_id}")
            return []
            
        # Kết nối MongoDB
        client = MongoClient("mongodb+srv://VieDev:durNBv9YO1TvPvtJ@cluster0.h4trl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
        db = client["techshop_db"]
        orders_collections = db["orders"]
        products_collections = db["products"]

        # Kịch bản 1: Người dùng cung cấp mã đơn hàng
        if order_id_from_slot:
            try:
                # Tìm chính xác đơn hàng theo _id và user_id (để bảo mật)
                order = orders_collections.find_one({
                    "_id": ObjectId(order_id_from_slot), 
                    "user": user_object_id
                })

                if not order:
                    dispatcher.utter_message(text=f"Không tìm thấy đơn hàng có mã '{order_id_from_slot}' hoặc đơn hàng này không phải của bạn.")
                    return []
                
                # Xây dựng message cho đơn hàng cụ thể
                message = f"""<p class="text-base">Đây là thông tin đơn hàng <strong>#{order_id_from_slot}</strong> của bạn:</p>"""
                message += """<div class="flex flex-col gap-8">"""
                message += self.build_order_html(order, products_collections)
                message += """</div>"""
                dispatcher.utter_message(text=message)

            except InvalidId:
                dispatcher.utter_message(text=f"Mã đơn hàng '{order_id_from_slot}' không hợp lệ. Vui lòng kiểm tra lại.")
            finally:
                client.close()
                return []
        
        # Kịch bản 2: Người dùng không cung cấp mã đơn hàng, hiển thị tất cả
        else:
            orders_info = list(orders_collections.find({"user": user_object_id}))

            if not orders_info:
                dispatcher.utter_message(text="Bạn chưa có đơn hàng nào, hãy mua hàng và trải nghiệm dịch vụ của hệ thống nhé!")
                client.close()
                return []
            
            message = """<p class="text-base">Aaaaa, tìm thấy rồi, bạn có các đơn hàng sau đây nè:</p>"""
            message += """<div class="flex flex-col gap-8">"""
            for order in orders_info:
                message += self.build_order_html(order, products_collections)
            message += """</div>"""
            dispatcher.utter_message(text=message)
            client.close()
            return []

    def build_order_html(self, order: Dict, products_collections) -> str:
        """Hàm trợ giúp để xây dựng HTML cho một đơn hàng."""
        order_html = ""
        # Thêm thông tin chung của đơn hàng
        order_html += f"""<div class="border border-gray-300 rounded-lg shadow-xs p-4 mb-4">
                            <h3 class="font-bold text-lg mb-2">Mã đơn hàng: {order['_id']}</h3>
                            <span class="block"><strong>Tổng tiền:</strong> {order.get('totalPrice', 'N/A'):,} VND</span>
                            <span class="block"><strong>Trạng thái:</strong> {order.get('status', 'N/A')}</span>
                            <hr class="my-2">
                            <p class="font-semibold">Chi tiết sản phẩm:</p>"""
        # Lặp qua các sản phẩm trong đơn
        for item in order.get("items", []):
            try:
                product = products_collections.find_one({"_id": item["product"]})
                if product:
                    order_html += f"""<div class="ml-4 mt-2">
                                        <span class="block"><strong>- Tên sản phẩm:</strong> {product.get("name", "Không rõ")}</span>
                                        <span class="block"><strong>&nbsp;&nbsp;Số lượng:</strong> {item.get("quantity", "N/A")}</span>
                                        <span class="block"><strong>&nbsp;&nbsp;Đơn giá:</strong> {item.get("price", 0):,} VND</span>
                                      </div>"""
            except InvalidId:
                continue # Bỏ qua nếu product ID không hợp lệ

        order_html += "</div>"
        return order_html