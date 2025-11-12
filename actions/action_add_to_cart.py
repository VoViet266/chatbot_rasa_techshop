import requests
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, AllSlotsReset
from bson import ObjectId
from utils.database import DatabaseService


class ActionAddToCart(Action):
    def name(self) -> str:
        return "action_add_to_cart"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        db_service = DatabaseService()

        # Lấy slot
        user_id = tracker.sender_id
        product_name = tracker.get_slot("product_name")
        variant_name = tracker.get_slot("variant_name")
        variant_color = tracker.get_slot("variant_color")
        quantity_str = tracker.get_slot("quantity")
        branch_id = tracker.get_slot("selected_branch_id")

        metadata = tracker.latest_message.get("metadata", {})
        token = metadata.get("accessToken")

        # 1. Kiểm tra đăng nhập
        if not user_id or not ObjectId.is_valid(user_id):
            dispatcher.utter_message(
                text="Quý khách vui lòng đăng nhập để sử dụng dịch vụ."
            )
            return []

        # 2. Tìm sản phẩm theo tên
        product_data = db_service.products_collection.find_one(
            {"name": {"$regex": f"{product_name}", "$options": "i"}}
        )

        if not product_data:
            dispatcher.utter_message(
                text=f"Sản phẩm '{product_name}' không tồn tại. Vui lòng chọn sản phẩm khác."
            )
            return [AllSlotsReset()]

        # 3. Lấy danh sách variant ID
        variant_ids = product_data.get("variants", [])
        if not variant_ids:
            dispatcher.utter_message(
                text=f"Sản phẩm {product_name} hiện không có phiên bản nào."
            )
            return [AllSlotsReset()]

        # 4. Tìm variant theo tên
        variant = db_service.variants_collection.find_one(
            {
                "_id": {"$in": variant_ids},
                "name": {"$regex": f"{variant_name}", "$options": "i"},
            }
        )

        if not variant:
            dispatcher.utter_message(
                text=f"Phiên bản {variant_name} của sản phẩm {product_name} không tồn tại."
            )
            return [SlotSet("product_name", product_name)]

        # 5. Kiểm tra màu trong variant
        if variant_color.startswith("màu "):
            variant_color = variant_color.replace("màu ", "", 1).strip()

        color_match = next(
            (
                c
                for c in variant.get("color", [])
                if c.get("colorName", "").strip().lower()
                == variant_color.strip().lower()
            ),
            None,
        )

        if not color_match:
            dispatcher.utter_message(
                text=f"Phiên bản {variant_name} không có màu {variant_color}."
            )
            return [
                SlotSet("product_name", product_name),
                SlotSet("variant_name", variant_name),
            ]

        # 6. Parse số lượng
        try:
            quantity = int(float(quantity_str))
            if quantity <= 0:
                quantity = 1
        except (ValueError, TypeError):
            quantity = 1

        # 7. Nếu chưa có chi nhánh, chọn hoặc hỏi người dùng
        if not branch_id:
            pipeline = [
                {
                    "$match": {
                        "product": product_data["_id"],
                        "isActive": True,
                        "variants": {
                            "$elemMatch": {
                                "variantId": variant["_id"],
                                "stock": {"$gte": quantity},
                            }
                        },
                    }
                },
                {
                    "$lookup": {
                        "from": "branches",
                        "localField": "branch",
                        "foreignField": "_id",
                        "as": "branchInfo",
                    }
                },
                {"$unwind": "$branchInfo"},
                {
                    "$project": {
                        "_id": 0,
                        "branch_id": "$branchInfo._id",
                        "branch_name": "$branchInfo.name",
                    }
                },
            ]

            available_branches = list(
                db_service.inventories_collection.aggregate(pipeline)
            )

            if not available_branches:
                dispatcher.utter_message(
                    text=f"Rất tiếc, sản phẩm {variant_name} - {variant_color} đã hết hàng hoặc không đủ số lượng {quantity} tại tất cả các chi nhánh."
                )
                return [AllSlotsReset()]

            if len(available_branches) == 1:
                branch_id = str(available_branches[0]["branch_id"])
            else:
                buttons = [
                    {
                        "title": branch["branch_name"],
                        "payload": f'/select_branch_cart{{"selected_branch_id": "{str(branch["branch_id"])}"}}',
                    }
                    for branch in available_branches
                ]

                dispatcher.utter_message(
                    text="Sản phẩm này có sẵn tại các chi nhánh sau. Bạn muốn thêm vào giỏ hàng từ chi nhánh nào?",
                    buttons=buttons,
                )

                return [
                    SlotSet("product_name", product_name),
                    SlotSet("variant_name", variant_name),
                    SlotSet("variant_color", variant_color),
                    SlotSet("quantity", quantity),
                ]

        # 8. Gửi dữ liệu đến API backend (đoạn này cậu tự viết logic gọi API)
        payload = {
            "items": [
                {
                    "product": str(product_data["_id"]),
                    "variant": str(variant["_id"]),
                    "color": variant_color,
                    "quantity": quantity,
                    "price": variant["price"],
                    "branch": branch_id,
                }
            ]
        }

        dispatcher.utter_message(
            text=f"Chuẩn bị thêm {quantity} x {product_name} ({variant_name} - {variant_color}) vào giỏ hàng."
        )

        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = requests.post(
                "http://localhost:8080/api/v1/carts",
                json=payload,
                headers=headers,
                timeout=10,
            )

            if response.status_code in [200, 201]:
                dispatcher.utter_message(
                    text=f"Đã thêm {quantity} x {product_name} ({variant_name} - {variant_color}) vào giỏ hàng thành công!"
                )
            else:
                dispatcher.utter_message(
                    text="Xin lỗi, đã có lỗi xảy ra khi thêm sản phẩm vào giỏ hàng."
                )
                print(f"Backend error: {response.status_code} - {response.text}")
        except Exception as e:
            dispatcher.utter_message(
                text="Đã có lỗi kết nối đến máy chủ. Vui lòng thử lại sau."
            )
            print(f"Error calling cart API: {e}")

        return [AllSlotsReset()]
