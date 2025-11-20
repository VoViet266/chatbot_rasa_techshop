from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from bson import ObjectId
from bson.errors import InvalidId
from typing import Any, Text, Dict, List
from datetime import datetime, time, timedelta
import dateparser
from dateparser.search import search_dates
from utils.database import DatabaseService


def _validate_user(tracker: Tracker, dispatcher: CollectingDispatcher) -> ObjectId:
    try:
        return ObjectId(tracker.sender_id)
    except (InvalidId, TypeError):
        dispatcher.utter_message(text="Bạn cần đăng nhập để xem thông tin đơn hàng.")
        return None



def _map_status_to_db(status_nlu: str) -> str:
    if not status_nlu:
        return None
    
    status_nlu = status_nlu.lower().strip()
    
    # Mapping chi tiết hơn
    mapping = {
        "chờ xác nhận": "PENDING",
        "chờ duyệt": "PENDING",
        "đang xử lý": "PROCESSING",
        "đang được xử lý": "PROCESSING",
        "đã xác nhận": "CONFIRMED",
        "đã duyệt": "CONFIRMED",
        "đang giao": "SHIPPING",
        "đang giao hàng": "SHIPPING",
        "đang vận chuyển": "SHIPPING",
        "đang ship": "SHIPPING",
        "đã giao": "DELIVERED",
        "đã giao hàng": "DELIVERED",
        "đã nhận": "DELIVERED",
        "hoàn thành": "DELIVERED",
        "đã huỷ": "CANCELLED",
        "đã hủy": "CANCELLED",
        "bị hủy": "CANCELLED",
        "bị huỷ": "CANCELLED",
        "đã thanh toán": "PAID",
        "chờ thanh toán": "PENDING_PAYMENT",
        "chưa thanh toán": "PENDING_PAYMENT",
    }
    
    # Tìm khớp chính xác trước
    if status_nlu in mapping:
        return mapping[status_nlu]
    
    # Tìm khớp một phần (contains)
    for key, value in mapping.items():
        if key in status_nlu or status_nlu in key:
            return value
    
    return None

def _get_time_query(time_str: str) -> Dict:
    if not time_str:
        return None
    
    time_str = time_str.strip()
    now = datetime.now()
    today_start = datetime.combine(now.date(), time.min)
    today_end = datetime.combine(now.date(), time.max)
    settings = {
        'PREFER_DATES_FROM': 'past',
        'RELATIVE_BASE': now,
        'TIMEZONE': 'Asia/Ho_Chi_Minh',
        'RETURN_AS_TIMEZONE_AWARE': False
    }

    special_cases = {
        'hôm nay': (today_start, today_end),
        'ngày hôm nay': (today_start, today_end),
        'hôm qua': (today_start - timedelta(days=1), today_start - timedelta(seconds=1)),
        'ngày hôm qua': (today_start - timedelta(days=1), today_start - timedelta(seconds=1)),
        
        'tuần này': (
            today_start - timedelta(days=today_start.weekday()),
            today_end
        ),
        'tuần trước': (
            today_start - timedelta(days=today_start.weekday() + 7),
            today_start - timedelta(days=today_start.weekday() + 1) - timedelta(seconds=1)
        ),
        'tháng này': (
            today_start.replace(day=1),
            today_end
        ),
        'tháng trước': (
            (today_start.replace(day=1) - timedelta(days=1)).replace(day=1),
            today_start.replace(day=1) - timedelta(seconds=1)
        ),
    }


    time_lower = time_str.lower()
    for key, (start, end) in special_cases.items():
        if key in time_lower:
            return {"createdAt": {"$gte": start, "$lte": end}}

    try:
        # Tìm ngày trong chuỗi
        dates_found = search_dates(time_str, languages=['vi'], settings=settings)
        
        if dates_found:
            # Lấy ngày đầu tiên tìm được
            parsed_date = dates_found[0][1]
            start = datetime.combine(parsed_date.date(), time.min)
            end = datetime.combine(parsed_date.date(), time.max)
            return {"createdAt": {"$gte": start, "$lte": end}}
        
        # Nếu không tìm thấy, thử parse trực tiếp
        parsed_date = dateparser.parse(time_str, languages=['vi'], settings=settings)
        if parsed_date:
            start = datetime.combine(parsed_date.date(), time.min)
            end = datetime.combine(parsed_date.date(), time.max)
            return {"createdAt": {"$gte": start, "$lte": end}}
            
    except Exception as e:
        print(f"[ERROR] Dateparser error: {e}")
    
    return None



def _format_status(status: str) -> str:
    status_map = {
        "PENDING": "Chờ xác nhận",
        "PROCESSING": "Đang xử lý",
        "CONFIRMED": "Đã xác nhận",
        "SHIPPING": "Đang giao hàng",
        "DELIVERED": "Đã giao hàng",
        "CANCELLED": "Đã hủy",
        "PAID": "Đã thanh toán",
        "PENDING_PAYMENT": "Chờ thanh toán",
    }
    return status_map.get(status, status)


def build_order_html(order: Dict, products_coll) -> str:
    product_ids = [item["product"] for item in order.get("items", []) if isinstance(item.get("product"), ObjectId)]
    product_map = {p["_id"]: p for p in products_coll.find({"_id": {"$in": product_ids}})} if product_ids else {}

    status = _format_status(order.get("status", ""))
    date_str = order["createdAt"].strftime("%d/%m/%Y %H:%M") if isinstance(order.get("createdAt"), datetime) else "Không rõ"

    html = f"""
    <div class="border border-gray-200 rounded-lg overflow-hidden mb-4 bg-white shadow-sm">
        <div class="p-4 border-b border-gray-300 bg-gray-50">
            <div class="flex justify-between items-center">
                <div>
                    <h3 class="font-bold text-base">Đơn hàng #{str(order['_id'])}</h3>
                    <p class="text-sm text-gray-500">{date_str}</p>
                </div>
                <text class="text-sm font-semibold px-3 py-1 ">{status}</text>
            </div>
        </div>
        <div class="p-4 flex flex-col gap-3">
    """

    for item in order.get("items", []):
        prod = product_map.get(item.get("product"))
        name = prod.get("name", "Không rõ") if prod else "Sản phẩm không tồn tại"
        price = f"{item.get('price', 0):,.0f} ₫"
        qty = item.get("quantity", 1)
        html += f"""
            <div class="flex justify-between items-center border-0">
                <span class="text-gray-700">{name} <span class="text-gray-500">x{qty}</span></span>
                <span class="font-medium">{price}</span>
            </div>
        """

    total = f"{order.get('totalPrice', 0):,.0f} ₫"
    html += f"""
        </div>
        <div class="bg-gray-50 p-4 flex justify-between items-center border-t border-gray-300">
            <span class="font-bold">Tổng cộng:</span>
            <span class="text-lg font-bold text-indigo-600">{total}</span>
        </div>
    </div>
    """
    return html



class ActionCheckOrderSpecific(Action):
    def name(self) -> Text:
        return "action_check_order_specific"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        db = DatabaseService()
        user_id = _validate_user(tracker, dispatcher)
        if not user_id:
            return []  

        order_id_str = tracker.get_slot("order_id")
        
        if order_id_str:
            order_id_str = order_id_str.strip().lstrip('#')

        if not order_id_str:
            dispatcher.utter_message(text="Bạn muốn xem thông tin của đơn hàng nào vậy? (Vui lòng cung cấp ID đơn hàng)")
            return []

        try:
            order_oid = ObjectId(order_id_str)
        except InvalidId:
            dispatcher.utter_message(text=f"Mã đơn hàng '{order_id_str}' trông không hợp lệ. Mã đơn hàng thường là một chuỗi 24 ký tự.")
            return [SlotSet("order_id", None)]

        try:
            # Query phải bao gồm cả user_id để đảm bảo bảo mật
            query = {
                "_id": order_oid,
                "user": user_id 
            }
            
            order = db.orders_collection.find_one(query)

            if not order:
                # Không tìm thấy đơn hàng, hoặc đơn hàng không thuộc về user này
                dispatcher.utter_message(text=f"Không tìm thấy đơn hàng nào của bạn có mã #{order_id_str}.")
                return [SlotSet("order_id", None)]

            # Nếu tìm thấy, build HTML và gửi
            message = f"<p class='text-base font-medium mb-3'>Đây là thông tin đơn hàng #{order_id_str} của bạn:</p>"
            message += build_order_html(order, db.products_collection)
            dispatcher.utter_message(text=message)

        except Exception:
            import traceback
            traceback.print_exc()
            dispatcher.utter_message(text="Xin lỗi, đã có lỗi xảy ra khi truy vấn thông tin đơn hàng. Vui lòng thử lại sau.")

        # Xóa slot sau khi hoàn thành
        return [SlotSet("order_id", None)]
    
class ActionCheckOrderFilter(Action):
    def name(self) -> Text:
        return "action_check_order_filter"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        db = DatabaseService()
        user_id = _validate_user(tracker, dispatcher)
        if not user_id:
            return []

        order_status = tracker.get_slot("order_status")
        time_str = tracker.get_slot("time")
        if not order_status and not time_str:
            dispatcher.utter_message(text="Bạn muốn lọc đơn hàng theo tiêu chí nào? (vd: đang giao, hôm qua, tháng này...)")
            return []

        # Build query
        query = {"user": user_id}
        title_parts = []
        
        # Lọc theo trạng thái
        if order_status:
            db_status = _map_status_to_db(order_status)
            
            if db_status:
                query["status"] = db_status
                title_parts.append(f"trạng thái '{order_status}'")
            else:
                dispatcher.utter_message(text=f"Xin lỗi, tôi không hiểu trạng thái '{order_status}'. Bạn có thể thử: đang giao, đã giao, đã hủy, chờ xác nhận...")
                return [SlotSet("order_status", None), SlotSet("time", None)]

        # Lọc theo thời gian
        if time_str:
            time_query = _get_time_query(time_str)
            
            if time_query:
                query.update(time_query)
                title_parts.append(f"thời gian '{time_str}'")
            else:
                dispatcher.utter_message(text=f"Xin lỗi, tôi không hiểu thời gian '{time_str}'. Bạn có thể thử: hôm nay, hôm qua, tuần này, tháng trước...")
                return [SlotSet("order_status", None), SlotSet("time", None)]


        try:
            orders = list(db.orders_collection.find(query).sort("createdAt", -1))
            
            if not orders:
                if title_parts:
                    msg = f"Không tìm thấy đơn hàng nào có {' và '.join(title_parts)}."
                else:
                    msg = "Không tìm thấy đơn hàng nào phù hợp với yêu cầu của bạn."
                dispatcher.utter_message(text=msg)
                return [SlotSet("order_status", None), SlotSet("time", None)]

            
            if title_parts:
                title = f"các đơn hàng có {' và '.join(title_parts)}"
            else:
                title = "các đơn hàng"

            
            message = f"<p class='text-base font-medium mb-3'>Đây là {title} của bạn ({len(orders)} đơn):</p>"
            message += "<div class='flex flex-col gap-4'>"
            
            for o in orders:
                message += build_order_html(o, db.products_collection)
            
            message += "</div>"
            dispatcher.utter_message(text=message)

        except Exception:
            import traceback
            traceback.print_exc()
            dispatcher.utter_message(text="Xin lỗi, đã có lỗi xảy ra khi truy vấn thông tin đơn hàng. Vui lòng thử lại sau.")

        return [SlotSet("order_status", None), SlotSet("time", None)]


class ActionCheckOrderGeneral(Action):
    def name(self) -> Text:
        return "action_check_order_general"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        db = DatabaseService()
        user_id = _validate_user(tracker, dispatcher)
        if not user_id:
            return []

        direction = tracker.get_slot("order_direction")
        index_val_str = tracker.get_slot("order_index") 

        query = {"user": user_id}
        
    
        if direction == "oldest":
            sort_order = [("createdAt", 1)] 
            title_direction = "cũ"
        else:
            sort_order = [("createdAt", -1)]
            title_direction = "mới"

        index_num = 1 
        if index_val_str:
            try:

                index_num = int(index_val_str)
                if index_num <= 0: 
                    index_num = 1
            except (ValueError, TypeError):
                index_num = 1 
        
        index_to_skip = index_num - 1

        if index_num == 1:
            title_index = "nhất"
        else:
            title_index = f"thứ {index_num}"

        title = f"{title_direction} {title_index}" 

        try:
            # 5. Query MongoDB bằng .skip() và .limit()
            cursor = db.orders_collection.find(query).sort(sort_order).skip(index_to_skip).limit(1)
            order = next(cursor, None) 

            if not order:
                if index_num == 1:
                    dispatcher.utter_message(text="Bạn chưa có đơn hàng nào cả.")
                else:
                    dispatcher.utter_message(text=f"Không tìm thấy đơn hàng {title} (thứ {index_num}) của bạn.")
            else:
                message = f"<p class='text-base font-medium mb-3'>Đây là đơn hàng {title} của bạn:</p>"
                message += build_order_html(order, db.products_collection)
                dispatcher.utter_message(text=message)

        except Exception :
            import traceback
            traceback.print_exc()
            dispatcher.utter_message(text="Xin lỗi, đã có lỗi xảy ra khi truy vấn thông tin đơn hàng. Vui lòng thử lại sau.")

        return [SlotSet("order_direction", None), SlotSet("order_index", None)]
    
class ActionCheckOrderByProduct(Action):
    def name(self) -> Text:
        return "action_check_order_by_product"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        db = DatabaseService()
        user_id = _validate_user(tracker, dispatcher)
        if not user_id:
            return []

        product_name = tracker.get_slot("product_name")
        if not product_name:
            dispatcher.utter_message(text="Bạn muốn xem đơn hàng của sản phẩm nào vậy?")
            return []

        try:
            # Tìm sản phẩm
            product = db.products_collection.find_one({"name": {"$regex": product_name, "$options": "i"}})
            if not product:
                dispatcher.utter_message(text=f"Tôi không tìm thấy sản phẩm nào tên '{product_name}'.")
                return [SlotSet("product_name", None)]
            
            product_id = product["_id"]

            # Tìm đơn hàng chứa sản phẩm đó
            query = {"user": user_id, "items.product": product_id}
            orders = list(db.orders_collection.find(query).sort("createdAt", -1))

            if not orders:
                dispatcher.utter_message(text=f"Không tìm thấy đơn hàng nào của bạn có chứa sản phẩm '{product_name}'.")
                return [SlotSet("product_name", None)]

            message = f"<p class='text-base font-medium mb-3'>Đây là các đơn hàng của bạn có chứa sản phẩm '{product_name}' ({len(orders)} đơn):</p>"
            message += "<div class='flex flex-col gap-4'>"
            for o in orders:
                message += build_order_html(o, db.products_collection)
            message += "</div>"
            dispatcher.utter_message(text=message)

        except Exception:
            import traceback
            traceback.print_exc()
            dispatcher.utter_message(text="Xin lỗi, đã có lỗi xảy ra khi truy vấn thông tin đơn hàng.")

        return [SlotSet("product_name", None)]
    
class ActionCheckUnpaidOrUnshippedOrders(Action):
    def name(self) -> Text:
        return "action_check_unpaid_or_unshipped_orders"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        db = DatabaseService()
        user_id = _validate_user(tracker, dispatcher)
        if not user_id:
            return []

        text = (tracker.latest_message.get("text") or "").lower()

        # Xác định loại lọc tự động
        if "chưa thanh toán" in text or "chờ thanh toán" in text:
            status = "PENDING_PAYMENT"
            label = "chưa thanh toán"
        elif "đang giao" in text or "chưa nhận" in text:
            status = "SHIPPING"
            label = "đang giao"
        else:
            dispatcher.utter_message(text="Bạn muốn xem đơn chưa thanh toán hay đơn đang giao?")
            return []

        try:
            query = {"user": user_id, "status": status}
            orders = list(db.orders_collection.find(query).sort("createdAt", -1))

            if not orders:
                dispatcher.utter_message(text=f"Bạn không có đơn hàng nào {label}.")
                return []

            message = f"<p class='text-base font-medium mb-3'>Đây là các đơn hàng {label} của bạn:</p>"
            message += "<div class='flex flex-col gap-4'>"
            for o in orders:
                message += build_order_html(o, db.products_collection)
            message += "</div>"
            dispatcher.utter_message(text=message)

        except Exception:
            import traceback
            traceback.print_exc()
            dispatcher.utter_message(text="Đã xảy ra lỗi khi kiểm tra đơn hàng.")

        return []
class ActionListRecentOrders(Action):
    def name(self) -> Text:
        return "action_list_recent_orders"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        db = DatabaseService()
        user_id = _validate_user(tracker, dispatcher)
        if not user_id:
            return []

        limit_val = tracker.get_slot("order_limit")
        try:
            limit = int(limit_val) if limit_val else 5
            if limit <= 0:
                limit = 5
        except (TypeError, ValueError):
            limit = 5

        try:
            orders = list(db.orders_collection.find({"user": user_id}).sort("createdAt", -1).limit(limit))

            if not orders:
                dispatcher.utter_message(text="Bạn chưa có đơn hàng nào.")
                return []

            message = f"<p class='text-base font-medium mb-3'>Đây là {limit} đơn hàng gần đây của bạn:</p>"
            message += "<div class='flex flex-col gap-4'>"
            for o in orders:
                message += build_order_html(o, db.products_collection)
            message += "</div>"
            dispatcher.utter_message(text=message)

        except Exception:
            import traceback
            traceback.print_exc()
            dispatcher.utter_message(text="Đã có lỗi khi truy xuất danh sách đơn hàng.")

        return [SlotSet("order_limit", None)]
