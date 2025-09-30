class ActionSubmitOrder:
    def name(self) -> str:
        return "action_submit_order"

    def run(self, dispatcher, tracker, domain):
        # Logic to process the order
        product = tracker.get_slot("product")
        full_name = tracker.get_slot("full_name")
        phone_number = tracker.get_slot("phone_number")
        address = tracker.get_slot("address")
        quantity = tracker.get_slot("quantity")
        payment_method = tracker.get_slot("payment_method")

        print(f"Order Details:\nProduct: {product}\nFull Name: {full_name}\nPhone Number: {phone_number}\nAddress: {address}\nQuantity: {quantity}\nPayment Method: {payment_method}")
        return []