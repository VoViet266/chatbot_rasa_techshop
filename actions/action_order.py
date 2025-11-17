from typing import Any, Text, Dict, List, Tuple, Optional
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, AllSlotsReset
from utils.database import DatabaseService
from bson import ObjectId
import regex
import requests
from utils.format_currentcy import format_vnd
from utils.product_pipelines import build_search_pipeline
import re

def _get_validated_order_info(tracker: Tracker, db_service: DatabaseService) -> Tuple[Optional[str], Optional[Dict]]:
    user_id = tracker.sender_id
    
    # 1. Xác thực người dùng
    if not user_id or not ObjectId.is_valid(user_id):
        return "Để mua hàng, vui lòng đăng nhập.", None
    
    product_name = tracker.get_slot("product")
    variant_name = tracker.get_slot("variant_name")
    quantity_str = tracker.get_slot("quantity")

    user_info = db_service.users_collection.find_one({"_id": ObjectId(user_id)})
    
    if not user_info:
        return "Không tìm thấy thông tin người dùng. Vui lòng thử đăng nhập lại.", None
    
    phone_number = user_info.get("phone", "")
    if not regex.match(r'^(0|\+84)(3[2-9]|5[6|8|9]|7[0|6-9]|8[1-5]|9[0-4|6-9])[0-9]{7}$', phone_number):
        return "Số điện thoại của bạn không hợp lệ. Vui lòng cập nhật lại thông tin cá nhân.", None
    
    # 2. Xác thực sản phẩm
    pipeline =  build_search_pipeline(product_name)
    product_data = next(db_service.products_collection.aggregate(pipeline), None)
    if not product_data:
        return f"Xin lỗi, tôi không tìm thấy sản phẩm '{product_name}'. Vui lòng kiểm tra lại.", None
    # 3. Xác thực phiên bản 
    variant_ids = product_data.get("variants", [])
    variants_cursor = db_service.variants_collection.find({"_id": {"$in": variant_ids}})
    
    found_variant = None
    for v in variants_cursor:
        if variant_name.lower() in v["name"].lower():
            found_variant = v
            break
            
    if not found_variant:
        return f"Xin lỗi, tôi không tìm thấy phiên bản '{variant_name}' cho sản phẩm {product_name}.", None
    
    variant_id = found_variant["_id"]
    
    # 4. Truy vấn tồn kho và chi nhánh
    pipeline = [
        {
            "$match": {
                "product": product_data["_id"],
                "isActive": True,
                "variants": {
                    "$elemMatch": {
                        "variantId": variant_id,
                        "stock": {"$gt": 0}
                    }
                }
            }
        },
        {
            "$lookup": {
                "from": "branches",
                "localField": "branch",
                "foreignField": "_id",
                "as": "branchInfo"
            }
        },
        {"$unwind": "$branchInfo"},
        {
            "$project": {
                "_id": 0,
                "branch_id": "$branchInfo._id",
                "branch_name": "$branchInfo.name",
                "branch_address": "$branchInfo.address",
                "variant_stock": {
                    "$arrayElemAt": [
                        {
                            "$map": {
                                "input": {
                                    "$filter": {
                                        "input": "$variants",
                                        "as": "v",
                                        "cond": {"$eq": ["$$v.variantId", variant_id]}
                                    }
                                },
                                "as": "filtered",
                                "in": "$$filtered.stock"
                            }
                        },
                        0
                    ]
                }
            }
        }
    ]

    available_branches_cursor = db_service.inventories_collection.aggregate(pipeline)
    available_branches = list(available_branches_cursor)

    if not available_branches:
        return f"Xin lỗi, sản phẩm {product_name} - {variant_name} hiện đã hết hàng tại tất cả các chi nhánh.", None
    
    # 5. Xác thực số lượng
    try:
        quantity = int(float(quantity_str))
        if quantity <= 0:
            quantity = 1
    except (ValueError, TypeError):
        quantity = 1
    
    # 6. Lấy địa chỉ mặc định
    addresses = user_info.get("addresses", [])
    default_address_obj = next((addr for addr in addresses if addr.get("default")), None)
    if default_address_obj:
        address_str = f'{default_address_obj["specificAddress"]}, {default_address_obj["addressDetail"]}'
    else:
        address_str = "Chưa có địa chỉ mặc định."

    # 7. Tính toán và trả về dữ liệu
    total_price = found_variant.get("price", 0) * quantity
    
    validated_data = {
        "user_id": user_id,
        "full_name": user_info.get("name", "N/A"),
        "phone_number": phone_number,
        "address": address_str,
        "product_name": product_data["name"],
        "product_id": str(product_data["_id"]),
        "variant_name": found_variant["name"],
        "variant_id": str(found_variant["_id"]),
        "variant_price": found_variant.get("price", 0),
        "quantity": quantity,
        "total_price": total_price,
        "available_branches": available_branches
    }
    
    return None, validated_data


class ActionReviewOrder(Action):
    def name(self) -> Text:
        return "action_preview_order"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        db_service = DatabaseService()
        error_message, order_data = _get_validated_order_info(tracker, db_service)

        if error_message:
            dispatcher.utter_message(text=error_message)
            return [AllSlotsReset()]

        available_branches = order_data.get("available_branches", [])
        
        # Trường hợp 1: Có nhiều chi nhánh
        if len(available_branches) > 1:
            # Tạo buttons để chọn chi nhánh
            buttons = []
            for branch in available_branches:
                buttons.append({
                    "title": f"{branch['branch_name']}",
                    "payload": f'/select_branch_order{{"selected_branch_id": "{str(branch["branch_id"])}"}}',
                })
            
            # Gửi message kèm buttons
            dispatcher.utter_message(text=(
        f"<div style='line-height:1.6; font-size:15px;'>"
        f"<b>Sản phẩm:</b> <span style='color:#0078D7;'>{order_data['product_name']} - {order_data['variant_name']}</span>"
        f"<b>Vui lòng chọn chi nhánh bạn muốn đặt hàng:</b>"
        f"</div>"
            ),
        buttons=buttons)              
            
            return [
                SlotSet("validated_product_id", order_data["product_id"]),
                SlotSet("validated_variant_id", order_data["variant_id"]),
                SlotSet("validated_quantity", order_data["quantity"]),
                SlotSet("validated_price", order_data["variant_price"]),
                SlotSet("validated_total_price", order_data["total_price"]),
                SlotSet("validated_address", order_data["address"]),
                SlotSet("validated_customer_name", order_data["full_name"]),
                SlotSet("validated_phone", order_data["phone_number"])
            ]

        # Trường hợp 2: Chỉ có 1 chi nhánh
        if len(available_branches) == 1:
            selected_branch = available_branches[0]
            selected_branch_id = str(selected_branch["branch_id"])
            selected_branch_name = selected_branch["branch_name"]

            summary_message = (
                f"**Vui lòng xác nhận lại thông tin đơn hàng của bạn:**\n\n"
                f"- Sản phẩm: **{order_data['product_name']}**\n"
                f"- Phiên bản: **{order_data['variant_name']}**\n"
                f"- Số lượng: **{order_data['quantity']}**\n"
                f"- Đặt từ chi nhánh: **{selected_branch_name}**\n"
                f"- Tổng cộng: **{format_vnd(order_data['total_price'])}**\n\n"
                f"**Thông tin giao hàng:**\n"
                f"- Người nhận: {order_data['full_name']}\n"
                f"- Số điện thoại: {order_data['phone_number']}\n"
                f"- Địa chỉ: {order_data['address']}\n\n"
                f"Bạn có muốn xác nhận đặt hàng không?"
            )
            dispatcher.utter_message(text=summary_message, buttons=[
                {
                    "title": "Tôi xác nhận đơn hàng",
                    "payload": '/confirm_order',
                }, 
                {
                    "title": "Tôi muốn hủy đơn hàng",
                    "payload": '/cancel',
                }
            ]
                
                
            )
            
            return [
                SlotSet("validated_product_id", order_data["product_id"]),
                SlotSet("validated_variant_id", order_data["variant_id"]),
                SlotSet("validated_quantity", order_data["quantity"]),
                SlotSet("validated_price", order_data["variant_price"]),
                SlotSet("validated_total_price", order_data["total_price"]),
                SlotSet("validated_address", order_data["address"]),
                SlotSet("validated_customer_name", order_data["full_name"]),
                SlotSet("validated_phone", order_data["phone_number"]),
                SlotSet("validated_branch_id", selected_branch_id)
            ]
            
        # Trường hợp 0 chi nhánh
        dispatcher.utter_message(text="Rất tiếc, sản phẩm này hiện không có sẵn ở bất kỳ chi nhánh nào.")
        return [AllSlotsReset()]


class ActionConfirmAfterBranch(Action):
    def name(self) -> Text:
        return "action_confirm_after_branch"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Lấy branch_id từ slot hoặc entity
        branch_id = tracker.get_slot("selected_branch_id")
        if not branch_id:
            branch_id = next(tracker.get_latest_entity_values("selected_branch_id"), None)     
        if not branch_id:
            dispatcher.utter_message(text="Đã có lỗi xảy ra khi chọn chi nhánh. Vui lòng thử lại.")
            return []

        # Lấy thông tin từ slots
        product_name = tracker.get_slot("product")
        variant_name = tracker.get_slot("variant_name")
        quantity = tracker.get_slot("validated_quantity")
        total_price = tracker.get_slot("validated_total_price")

        # Truy vấn DB để lấy tên chi nhánh
        db_service = DatabaseService()
        branch_info = db_service.branches_collection.find_one({"_id": ObjectId(branch_id)})
        branch_name = branch_info.get("name") if branch_info else "Chi nhánh đã chọn"

        summary_message = (
            "<b>Vui lòng xác nhận lại thông tin đơn hàng của bạn:</b><br><br>"
            f"- Sản phẩm: <b>{product_name}</b><br>"
            f"- Phiên bản: <b>{variant_name}</b><br>"
            f"- Số lượng: <b>{quantity}</b><br>"
            f"- Đặt từ chi nhánh: <b>{branch_name}</b><br>"
            f"- Tổng cộng: <b>{format_vnd(total_price)}</b><br><br>"
            "<b>Thông tin giao hàng:</b><br>"
            f"- Người nhận: {tracker.get_slot('validated_customer_name')}<br>"
            f"- Số điện thoại: {tracker.get_slot('validated_phone')}<br>"
            f"- Địa chỉ: {tracker.get_slot('validated_address')}<br><br>"
            "Bạn có muốn xác nhận đặt hàng không?"
        )
        dispatcher.utter_message(text=summary_message,  buttons=[
            {
                "title": "Tôi xác nhận đơn hàng",
                "payload": '/confirm_order',
            }, 
            {
                "title": "Tôi muốn hủy tiến trình đặt hàng",
                "payload": '/cancel',
            }
        ])
        return [SlotSet("validated_branch_id", branch_id)]


class ActionSubmitOrder(Action):
    def name(self) -> Text:
        return "action_submit_order"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Lấy thông tin từ slots
        user_id = tracker.sender_id
        metadata = tracker.latest_message.get("metadata", {})
        token = metadata.get("accessToken")

        product_id = tracker.get_slot("validated_product_id")
        variant_id = tracker.get_slot("validated_variant_id")
        price = tracker.get_slot("validated_price")
        quantity = tracker.get_slot("validated_quantity")
        total_price = tracker.get_slot("validated_total_price")
        address = tracker.get_slot("validated_address")
        customer_name = tracker.get_slot("validated_customer_name")
        phone = tracker.get_slot("validated_phone")
        branch_id = tracker.get_slot("validated_branch_id")
        
        # Kiểm tra thông tin đầy đủ
        if not all([product_id, variant_id, quantity, branch_id]):
            dispatcher.utter_message(
                text="Đã có lỗi xảy ra. Thông tin đơn hàng không đầy đủ. Vui lòng thử lại từ đầu."
            )
            return [AllSlotsReset()]

        # Tạo payload đơn hàng
        order_payload = {
            "user": user_id,
            "recipient": {
                "name": customer_name,
                "phone": phone,
                "address": address,
            },
            "buyer": { 
                "name": customer_name,
                "phone": phone,
            },
            "items": [{
                "product": product_id,
                "variant": variant_id,
                "quantity": quantity,
                "price": price,
                "branch": branch_id
            }],
            "totalPrice": total_price,
            "shippingAddress": address,
            "phone": phone,
            "customerName": customer_name,
            "status": "pending"
        }
        
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            
        try:
            response = requests.post(
                "http://localhost:8080/api/v1/orders", 
                json=order_payload, 
                headers=headers, 
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                order_id = response.json().get("data", {}).get("_id", "N/A")
                dispatcher.utter_message(
                    text=f"Đặt hàng thành công! Mã đơn hàng của bạn là **#{order_id}**."
                )
            else:
                dispatcher.utter_message(
                    text="Xin lỗi, đã có lỗi xảy ra khi gửi đơn hàng đến hệ thống."
                )
                print(f"Backend error: {response.status_code} - {response.text}")
        except Exception as e:
            dispatcher.utter_message(
                text="Đã có lỗi kết nối đến máy chủ. Vui lòng thử lại sau."
            )
            print(f"Error submitting order: {str(e)}")
            
        return [AllSlotsReset()]


class ActionCancelOrderingProcess(Action):
    def name(self) -> Text:
        return "action_cancel_ordering_process"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(
            text="Đã dừng tiến trình đặt hàng. Nếu bạn muốn đặt lại, chỉ cần nói 'Tôi muốn mua hàng' nhé."
        )
        return [AllSlotsReset()]


class ActionCancelOrder(Action):
    def name(self) -> Text:
        return "action_cancel_order"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        metadata = tracker.latest_message.get("metadata", {})
        token = metadata.get("accessToken")
        order_id = tracker.get_slot("order_id")
        # Nếu không có mã đơn => yêu cầu người dùng nhập
        if not order_id:
            text = tracker.latest_message.get("text", "")
            match = re.search(r"[0-9a-fA-F]{24}", text)
            if match:
                order_id = match.group(0)
        if not order_id:
            dispatcher.utter_message(text="Vui lòng cung cấp mã đơn hàng bạn muốn hủy.")
            return []

        db = DatabaseService()
        order =  db.orders_collection.find_one({"_id": ObjectId(order_id)})

        if not order:
            dispatcher.utter_message(text=f"Không tìm thấy đơn hàng có mã {order_id}.")
            return []

        status = (order.get("status") or "").upper()
        if status != "PENDING":
            dispatcher.utter_message(
                text=f"Đơn hàng {order_id} hiện ở trạng thái '{status}' nên không thể hủy. Chỉ đơn đang chờ xử lý (PENDING) mới được hủy."
            )
            return []
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            response = requests.patch(
                f"http://localhost:8080/api/v1/orders/cancel/{order_id}",
                headers=headers,
                timeout=10,
            )
            if response.status_code in (200, 201):
                dispatcher.utter_message(text=f"Đơn hàng {order_id} đã được hủy thành công.")
                return [AllSlotsReset()]
            elif response.status_code == 401:
                dispatcher.utter_message(text="Bạn cần đăng nhập để hủy đơn hàng này.")
            else:
                dispatcher.utter_message(text="Không thể hủy đơn hàng lúc này. Vui lòng thử lại sau.")
        except Exception as e:
            print("Error cancelling order:", str(e))
            dispatcher.utter_message(text="Không thể kết nối đến hệ thống. Vui lòng thử lại sau.")
        
        return []
