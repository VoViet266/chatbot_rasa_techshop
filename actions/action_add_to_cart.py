import requests
from pymongo import MongoClient
from rasa_sdk.events import SlotSet, AllSlotsReset
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

class ActionAddToCart(Action):
    def name(self) -> str:
        return "action_add_to_cart"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):

        # Lấy slot hiện tại
        user_id = tracker.sender_id
        variant_color = tracker.get_slot("variant_color")
        variant_name = tracker.get_slot("variant_name_add")
        quantity = tracker.get_slot("quantity")
        product_name = tracker.get_slot("product")
        metadata = tracker.latest_message.get("metadata", {})
        token = metadata.get("accessToken")

        client = MongoClient("mongodb+srv://VieDev:durNBv9YO1TvPvtJ@cluster0.h4trl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
        database = client["techshop_db"]
        product_model = database["products"]
        variant_model = database["variants"]

        # Kiểm tra người dùng đã đăng nhập hay chưa
        if not user_id:
            dispatcher.utter_message(text="Quý khách vui lòng đăng nhập để sử dụng dịch vụ?")
            return []

        # Tạo dữ liệu gửi đi
        payload = { 'items': [] }

        # Bước 1: Nếu chưa có product, hỏi
        if not product_name:
            dispatcher.utter_message(text="Bạn muốn thêm sản phẩm nào vào giỏ hàng?")
            return []

        # Bước 2: Kiểm tra sản phẩm có tồn tại không
        product = product_model.find_one({"name": {"$regex": product_name, "$options": "i"}})
        
        if not product:
            dispatcher.utter_message(text="Sản phẩm quý khách muốn thêm hiện không tồn tại trên hệ thống. Xin quý khách vui lòng lựa chọn một sản phẩm khác!")
        

        # Bước 3: Nếu chưa có variant
        if not variant_name:
            dispatcher.utter_message(text=f"Bạn muốn chọn phiên bản nào cho {product_name}?")
            return []

        # print('Variant name:', variant_name)

        # Bước 4: Nếu chưa có color
        if not variant_color:
            dispatcher.utter_message(text=f"Bạn muốn chọn màu gì cho {variant_name}?")
            return []
        
        # print('Variant color:', variant_color)
        
        variant_id = None
        for variant_id in product['variants']:
            variant = variant_model.find_one({
                "_id": variant_id,
                "name": {"$regex": variant_name, "$options": "i"},
                "color": {"$elemMatch": {"colorName": variant_color}}
            })
            if variant:
                variant_id = variant['_id']
                print("Variant:", variant)
                break

        # Bước 5: Nếu chưa có quantity
        if not quantity:
            dispatcher.utter_message(text="Bạn muốn thêm bao nhiêu sản phẩm?")
            return []
        
        payload["items"].append({ 'product': str(product['_id']), 'variant': str(variant_id), 'quantity': int(quantity) })

        print('Payload:', payload)

        # Bước 6: Khi đủ thông tin → Gọi API thêm giỏ hàng
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = requests.post("http://localhost:8080/api/v1/carts", json=payload, headers=headers, timeout=10)
            if response.status_code in [200, 201]:
                dispatcher.utter_message(text=f"Hành động thêm vào giỏ hàng đã được thực hiện thành công!.")
            else:
                dispatcher.utter_message(text="Xin lỗi, đã có lỗi xảy ra trong quá trình thực hiện hành động thêm vào giỏ hàng .")
                print(f"Backend error: {response.status_code} - {response.text}")
        except Exception as e:
            dispatcher.utter_message(text="Đã có lỗi kết nối đến máy chủ. Vui lòng thử lại sau.")
        return [AllSlotsReset()]
