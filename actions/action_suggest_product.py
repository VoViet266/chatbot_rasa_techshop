from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

class ActionSuggestProduct(Action):
    def name(self):
        return "action_suggest_product"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain):
        
        text = tracker.latest_message.get("text", "").lower()
        entities = tracker.latest_message.get("entities", [])
        numbers = [int(e["value"]) for e in entities if e["entity"] == "number"]

        min_price, max_price = None, None

        print('Thằng người dùng nói:', text)
        print('Chạy dùm cái đi, khổ lắm rồi!')

        if "dưới" in text and numbers:
            max_price = numbers[0]
            print("Max price:", max_price)
        elif "trên" in text and numbers:
            min_price = numbers[0]
            print("Min price:", min_price)
        elif "đến" in text and len(numbers) == 2:
            min_price, max_price = min(numbers), max(numbers)
            print("Min price:", min_price, "Max price:", max_price)

        # 👉 Sau đó truy vấn database hoặc gọi API gợi ý sản phẩm
        # if max_price and not min_price:
        #     dispatcher.utter_message(text=f"Gợi ý các mẫu laptop giá dưới {max_price} triệu...")
        # elif min_price and not max_price:
        #     dispatcher.utter_message(text=f"Gợi ý các mẫu laptop giá trên {min_price} triệu...")
        # elif min_price and max_price:
        #     dispatcher.utter_message(text=f"Gợi ý các mẫu laptop giá từ {min_price} đến {max_price} triệu...")
        # else:
        #     dispatcher.utter_message(text="Bạn muốn tầm giá khoảng bao nhiêu vậy?")
        dispatcher.utter_message(text="Bạn muốn tầm giá khoảng bao nhiêu vậy?")
        
        return []
