from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import requests
from utils.render_product_ui import render_products
from utils.database import DatabaseService
from bson import ObjectId
from rasa_sdk.events import AllSlotsReset, SlotSet

BACKEND_URL = "http://localhost:8080/api/v1"

class ActionGetRecommendation(Action):
    def name(self) -> Text:
        return "action_get_recommendation"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        product_name = tracker.get_slot("product_name")
        recommendations = []
        metadata = tracker.latest_message.get("metadata", {})
        token = metadata.get("accessToken")
        try:
            if product_name:
                # Resolve product name to ID
                db = DatabaseService()
                product = db.products_collection.find_one(
                    {"name": {"$regex": product_name, "$options": "i"}}
                )                
                if product:
                    product_id = str(product["_id"])
                    print("có pro duct")
                    print(product["name"])
                    # Content-based recommendation
                    response = requests.get(f"{BACKEND_URL}/recommend/{product_id}?limit=5")
                    if response.status_code == 200:
                        json_response = response.json()
                        recommendations = json_response.get("data", [])
                    else:
                        print(f"API Error: {response.status_code} - {response.text}")
                else:
                    dispatcher.utter_message(text=f"Xin lỗi, mình không tìm thấy sản phẩm '{product_name}' để gợi ý tương tự.")
                    return [AllSlotsReset()]
            else:
                # User-based recommendation or Popular fallback
                user_id = tracker.sender_id
                user_recommendations = []
            
                # Try to get user-based recommendations if user_id is valid
                if user_id and ObjectId.is_valid(user_id):
                    headers = {"Content-Type": "application/json"}
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    try:
                        print(f"Fetching recommendations for user: {user_id}")
                        response = requests.get(f"{BACKEND_URL}/recommend/get-by-user/{user_id}", headers= headers)
                        if response.status_code == 200:
                            json_response = response.json()
                            
                            user_recommendations = json_response.get("data", [])
                    except Exception as e:
                        print(f"Error fetching user recommendations: {e}")

                if user_recommendations:
                    recommendations = user_recommendations
                else:
                
                    response = requests.get(f"{BACKEND_URL}/recommend/recommendation/get-popular?limit=5")
                    if response.status_code == 200:
                        json_response = response.json()
                        recommendations = json_response.get("data", [])
                    else:
                        print(f"API Error: {response.status_code} - {response.text}")

            if not recommendations:
                dispatcher.utter_message(text="Hiện tại mình chưa có gợi ý nào phù hợp.")
                return [AllSlotsReset()]

            html = render_products(recommendations)
            dispatcher.utter_message(text=html)
            
        except Exception as e:
            print(f"Error in action_get_recommendation: {e}")
            dispatcher.utter_message(text="Có lỗi xảy ra khi lấy gợi ý sản phẩm.")

        return [SlotSet("product_name", None)]
