import pymongo
import logging
from rasa_sdk import Action, Tracker
from bson import ObjectId
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet # <-- Thêm import này
from typing import Any, Text, Dict, List
import re
from collections import defaultdict 

# Thiết lập logger
logger = logging.getLogger(__name__)

class ActionCheckStock(Action):
    def name(self) -> Text:
        return "action_check_stock"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # 1. Lấy thông tin từ các slots
        product_name = tracker.get_slot("product")
        variant_name = tracker.get_slot("variant_name")
        branch_name = tracker.get_slot("branch_name") 

        if not product_name:
            dispatcher.utter_message(text="Bạn muốn kiểm tra tồn kho cho sản phẩm nào ạ?")
            return []
        
        client = pymongo.MongoClient("mongodb+srv://VieDev:durNBv9YO1TvPvtJ@cluster0.h4trl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
        
        # Danh sách các sự kiện trả về (để reset slot)
        events_to_return = [
            SlotSet("variant_name", None),
            SlotSet("branch_name", None)
        ]
        
        try:
            db = client["techshop_db"]
            products_collection = db["products"]
            inventory_collection = db["inventories"] 
            branches_collection = db["branches"] 

            product_doc = products_collection.find_one({
                "name": {"$regex": f"^{re.escape(product_name)}$", "$options": "i"}
            })

            if not product_doc:
                dispatcher.utter_message(text=f"Xin lỗi, tôi không tìm thấy sản phẩm nào có tên là '{product_name}'.")
                return events_to_return # Trả về

            product_id = product_doc["_id"]
            product_name_proper = product_doc.get("name", product_name) 

            inventory_query = {"product": product_id}
            scope_message = "trên toàn hệ thống" 
            branch_name_proper = None
            
            if branch_name:
                branch_doc = branches_collection.find_one({
                    "name": {"$regex": f"{re.escape(branch_name)}", "$options": "i"} 
                })
                
                if not branch_doc:
                    dispatcher.utter_message(text=f"Xin lỗi, tôi không tìm thấy chi nhánh nào có tên là '{branch_name}'.")
                    return events_to_return # Trả về
                
                branch_id = branch_doc["_id"]
                branch_name_proper = branch_doc.get("name", branch_name)
                
                inventory_query["branch"] = branch_id 
                scope_message = f"tại chi nhánh <strong>{branch_name_proper}</strong>"

            
            inventory_docs = list(inventory_collection.find(inventory_query))

            if not inventory_docs:
                message = f"""<div class="p-4 bg-yellow-50 border border-yellow-200 rounded-lg>
                                  <h4 class="font-bold text-gray-800 mb-2">❌ Chưa có hàng</h4>
                                  <p class="text-gray-700">
                                    Sản phẩm <strong class="text-blue-600">{product_name_proper}</strong>
                                    hiện chưa được nhập kho {scope_message}.
                                  </p>
                                </div>"""
                dispatcher.utter_message(text=message)
                return events_to_return # Trả về

            variant_stock_map = defaultdict(int)
            
            for doc in inventory_docs:
                for variant in doc.get("variants", []):
                    color = variant.get("variantColor", "N/A")
                    stock = variant.get("stock", 0)
                    variant_stock_map[color] += stock
            
            if variant_name:
                variant_found = False
                matched_color = None
                matched_stock = 0

                for color, stock in variant_stock_map.items():
                    if variant_name.lower() in color.lower():
                        variant_found = True
                        matched_color = color
                        matched_stock = stock
                        break
                
                if variant_found:
                    if matched_stock > 0:
                    
                        message = f"""<div class="p-4 bg-green-50 border border-green-200 rounded-lg >
                                      <h4 class="font-bold text-gray-800 mb-2">✅ Còn hàng!</h4>
                                      <p class="text-gray-700">
                                        Sản phẩm <strong class="text-blue-600">{product_name_proper}</strong>
                                        phiên bản <strong class="text-green-700">{matched_color}</strong>
                                        hiện còn <strong class="text-orange-600">{matched_stock}</strong> sản phẩm {scope_message}.
                                      </p>
                                      <p class="mt-3 text-sm text-gray-600"><em>Bạn có muốn đặt hàng ngay không?</em></p>
                                    </div>"""
                        dispatcher.utter_message(text=message)
                    else:
                     
                        message = f"""<div class="p-4 bg-yellow-50 border border-yellow-200 rounded-lg ">
                                      <h4 class="font-bold text-gray-800 mb-2">❌ Hết hàng tạm thời</h4>
                                      <p class="text-gray-700">
                                        Rất tiếc! Sản phẩm <strong class="text-blue-600">{product_name_proper}</strong>
                                        phiên bản <strong class="text-green-700">{matched_color}</strong>
                                        hiện đã <strong class="text-red-600">hết hàng</strong> {scope_message}.
                                      </p>
                                      <p class="mt-3 text-sm text-gray-600"><em>Bạn có muốn tôi thông báo khi có hàng trở lại không?</em></p>
                                    </div>"""
                        dispatcher.utter_message(text=message)
                else:
               
                    message = f"""<div class="p-4 bg-blue-50 border border-blue-200 rounded-lg shadow-sm">
                              <h4 class="font-bold text-gray-800 mb-2">ℹ️ Không tìm thấy phiên bản</h4>
                              <p class="text-gray-700">
                                Xin lỗi! Tôi không tìm thấy phiên bản <strong class="text-green-700">{variant_name}</strong>
                                cho sản phẩm <strong class="text-blue-600">{product_name_proper}</strong> {scope_message}.
                              </p>
                              <p class="mt-3 text-sm text-gray-600"><em>Vui lòng kiểm tra lại tên phiên bản.</em></p>
                            </div>"""
                    dispatcher.utter_message(text=message)

            else:
                total_stock = 0
                available_variants_html = []
                for color, stock in variant_stock_map.items():
                    if stock > 0:
                        total_stock += stock
                        available_variants_html.append(
                            f"<li class='text-sm'><strong class='text-green-700'>{color}</strong> (còn {stock} sản phẩm)</li>"
                        )
                
                if total_stock > 0:
                    
                    variants_list_html = "".join(available_variants_html)
                    message = f"""<div class="p-4 bg-white border border-gray-200 rounded-lg ">
                                  <h4 class="font-bold text-gray-800 mb-2">📦 Thông tin tồn kho: {product_name_proper}</h4>
                                  <p class="text-gray-700">
                                    Sản phẩm này {scope_message} còn tổng cộng <strong class="text-orange-600">{total_stock}</strong> sản phẩm.
                                  </p>
                                  <p class="mt-3 mb-2 font-medium text-gray-800">Các phiên bản còn hàng:</p>
                                  <ul class="list-disc list-inside text-gray-700 space-y-1">
                                    {variants_list_html}
                                  </ul>
                                  <p class="mt-4 text-sm text-gray-600"><em>Bạn muốn chọn phiên bản nào ạ?</em></p>
                                </div>"""
                    dispatcher.utter_message(text=message)
                else:
                   
                    message = f"""<div class="p-4 bg-yellow-50 border border-yellow-200 rounded-lg ">
                                  <h4 class="font-bold text-gray-800 mb-2">❌ Đã hết hàng</h4>
                                  <p class="text-gray-700">
                                    Rất tiếc! Sản phẩm <strong class="text-blue-600">{product_name_proper}</strong>
                                    hiện đã tạm hết hàng ở tất cả các phiên bản {scope_message}.
                                  </p>
                                </div>"""
                    dispatcher.utter_message(text=message)
        
        except Exception as e:
            logger.error(f"Lỗi trong ActionCheckStock: {e}")
            dispatcher.utter_message(text="Xin lỗi, tôi gặp lỗi khi kiểm tra kho, bạn vui lòng thử lại sau nhé.")

        finally:
            client.close() 
            
        return events_to_return # Trả về