import logging
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from pymongo import MongoClient
from urllib.parse import quote_plus  # Vẫn giữ lại để fallback

# Thiết lập logging
logger = logging.getLogger(__name__)

class ActionProvideStoreInfo(Action):
    def name(self):
        return "action_provide_store_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):

        try:
            # --- Kết nối MongoDB ---
            client = MongoClient("mongodb+srv://VieDev:durNBv9YO1TvPvtJ@cluster0.h4trl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
            db = client["techshop_db"]
            branches_collections = db["branches"]
            
            # --- Truy vấn dữ liệu ---
            branches_info = list(branches_collections.find({"isDeleted": False}))
            client.close() 

            if not branches_info:
                dispatcher.utter_message(text="Xin lỗi! Hiện chưa có bất kỳ chi nhánh nào.")
            else:
                message = f"""<p class="text-base mb-4">Hiện tại, hệ thống có các chi nhánh như sau:</p>"""
                message += """<div class="flex flex-col gap-6">"""
                
                for br in branches_info:
                    # Lấy thông tin an toàn bằng .get()
                    name = br.get("name", "N/A")
                    phone = br.get("phone", "N/A")
                    email = br.get("email", "N/A")
                    address_text = br.get("address", "N/A") 
                    location = br.get("location")
                    
                    map_link = "#" 

                    if (location and 
                        isinstance(location, dict) and 
                        location.get("coordinates") and 
                        len(location.get("coordinates")) == 2):
                        
                        # Schema của bạn là [longitude, latitude]
                        longitude = location["coordinates"][0]
                        latitude = location["coordinates"][1]  
                        map_link = f"https://www.google.com/maps?q={latitude},{longitude}"
                    elif address_text != "N/A":
                        encoded_address = quote_plus(address_text)
                        map_link = f"https://www.google.com/maps/search/?api=1&query={encoded_address}"
                    
                  
                    message += f"""<div class="border border-gray-100 rounded-lg  p-10 bg-white">
                                      <h3 class="text-lg font-semibold text-gray-600 mb-3">{name}</h3>
                                      <div class="flex flex-col gap-2 text-sm text-gray-700">
                                          <span class="flex items-center gap-2">
                                              <span class="text-lg">📞</span>
                                              <span>{phone}</span>
                                          </span>
                                          <span class="flex items-center gap-2">
                                              <span class="text-lg">✉️</span>
                                              <span>{email}</span>
                                          </span>
                                          <span class="flex items-start gap-2">
                                              <span class="text-lg mt-1">📍</span>
                                              <a href="{map_link}" target="_blank" rel="noopener noreferrer" 
                                                 class="text-blue-600 hover:text-blue-800 hover:underline text-justify">
                                                {address_text} 
                                              </a>
                                          </span>
                                      </div>
                                  </div>"""
                
                message += """<span class="block mt-4">Nếu muốn biết thêm thông tin chi tiết, đừng ngại hỏi nhé!</span></div>"""
                
                dispatcher.utter_message(text=message)

        except Exception as e:
            logger.error(f"Lỗi trong ActionProvideStoreInfo: {e}")
            dispatcher.utter_message(text="Xin lỗi, tôi đã gặp lỗi khi cố gắng lấy thông tin cửa hàng. Vui lòng thử lại sau.")

        return []