import logging
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from utils.database import DatabaseService
from urllib.parse import quote_plus

# Thiết lập logging
logger = logging.getLogger(__name__)

class ActionProvideStoreInfo(Action):
    def name(self):
        return "action_provide_store_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):

        try:
            # --- Kết nối MongoDB qua Service ---
            db = DatabaseService()
            
            # --- Truy vấn dữ liệu ---
            branches_info = list(db.branches_collection.find({"isDeleted": False}))

            if not branches_info:
                dispatcher.utter_message(text="Xin lỗi! Hiện chưa có bất kỳ chi nhánh nào đang hoạt động.")
            else:
                # Header
                message = """
                <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background-color: #d32f2f; color: white; padding: 12px 16px; border-radius: 8px 8px 0 0; display: flex; align-items: center;">
                        <span style="font-size: 20px; margin-right: 10px;">🏪</span>
                        <h3 style="margin: 0; font-size: 16px; font-weight: 600;">Hệ thống cửa hàng TechShop</h3>
                    </div>
                    <div style="border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 8px 8px; background-color: #fff; padding: 16px;">
                        <p style="margin: 0 0 16px 0; color: #555; font-size: 14px;">
                            Dưới đây là danh sách các chi nhánh hiện tại của chúng tôi:
                        </p>
                """
                
                for br in branches_info:
                    name = br.get("name", "Chi nhánh TechShop")
                    phone = br.get("phone", "N/A")
                    email = br.get("email", "N/A")
                    address_text = br.get("address", "N/A") 
                    location = br.get("location")
                    
                    # Giờ làm việc (Giả định nếu không có trong DB)
                    opening_hours = br.get("opening_hours", "8:00 - 21:00 (Hàng ngày)")

                    map_link = "#" 
                    if (location and isinstance(location, dict) and 
                        location.get("coordinates") and len(location.get("coordinates")) == 2):
                        longitude = location["coordinates"][0]
                        latitude = location["coordinates"][1]  
                        map_link = f"https://www.google.com/maps?q={latitude},{longitude}"
                    elif address_text != "N/A":
                        encoded_address = quote_plus(address_text)
                        map_link = f"https://www.google.com/maps/search/?api=1&query={encoded_address}"
                    
                    # Card cho từng chi nhánh
                    message += f"""
                    <div style="border: 1px solid #eee; border-radius: 8px; padding: 12px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                        <h4 style="margin: 0 0 8px 0; color: #d32f2f; font-size: 15px; font-weight: 600;">{name}</h4>
                        
                        <div style="font-size: 13px; color: #444; line-height: 1.6;">
                            <div style="display: flex; align-items: flex-start; margin-bottom: 4px;">
                                <span style="margin-right: 8px; min-width: 20px;">📍</span>
                                <a href="{map_link}" target="_blank" style="color: #1976d2; text-decoration: none;">{address_text}</a>
                            </div>
                            <div style="display: flex; align-items: center; margin-bottom: 4px;">
                                <span style="margin-right: 8px; min-width: 20px;">📞</span>
                                <span>{phone}</span>
                            </div>
                            <div style="display: flex; align-items: center; margin-bottom: 4px;">
                                <span style="margin-right: 8px; min-width: 20px;">✉️</span>
                                <span>{email}</span>
                            </div>
                            <div style="display: flex; align-items: center;">
                                <span style="margin-right: 8px; min-width: 20px;">🕒</span>
                                <span>{opening_hours}</span>
                            </div>
                        </div>
                    </div>
                    """
                
                # Footer
                message += """
                        <div style="margin-top: 12px; font-size: 13px; color: #777; text-align: center; border-top: 1px dashed #eee; padding-top: 12px;">
                            Bạn có thể ghé thăm chi nhánh gần nhất để trải nghiệm sản phẩm nhé!
                        </div>
                    </div>
                </div>
                """
                
                dispatcher.utter_message(text=message)

        except Exception as e:
            logger.error(f"Lỗi trong ActionProvideStoreInfo: {e}")
            dispatcher.utter_message(text="Xin lỗi, tôi đã gặp lỗi khi cố gắng lấy thông tin cửa hàng. Vui lòng thử lại sau.")

        return []