from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from bson import ObjectId
from utils.database import DatabaseService
import traceback
import os
from dotenv import load_dotenv

load_dotenv()


class ActionViewCart(Action):
    def name(self) -> str:
        return "action_view_cart"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        # Lấy user_id
        user_id = tracker.sender_id

        # 1. Kiểm tra đăng nhập
        if not user_id or not ObjectId.is_valid(user_id):
            dispatcher.utter_message(
                text="Quý khách vui lòng đăng nhập để sử dụng dịch vụ."
            )
            return []

        db_service = DatabaseService()
        cart = db_service.carts_collection.find_one({"user": ObjectId(user_id)})

        # Nếu không có giỏ hàng hoặc bị xóa
        if not cart or cart.get("isDeleted", False):
            dispatcher.utter_message(text="Giỏ hàng của bạn hiện đang trống.")
            return []

        items = cart.get("items", [])
        if not items:
            dispatcher.utter_message(text="Giỏ hàng của bạn hiện đang trống.")
            return []

        # Build HTML for cart items
        cart_html_items = ""
        true_total = 0
        
        # Display all items (no limit)
        for item in items:
            try:
                # 1. Get Product
                product_id = item.get("product")
                if isinstance(product_id, str):
                    product_id = ObjectId(product_id)
                
                product = db_service.products_collection.find_one({"_id": product_id})
                
                if not product:
                    print(f"Product not found for ID: {product_id}")
                    continue

                # 2. Get Variant
                variant = None
                variant_id = item.get("variant")
                variant_name = ""
                
                if variant_id:
                    if isinstance(variant_id, str):
                        variant_id = ObjectId(variant_id)
                    variant = db_service.variants_collection.find_one({"_id": variant_id})
                
                # 3. Construct Variant Name
                if variant:
                    v_specs = []
                    # Color
                    item_color = item.get("color") # Color name stored in cart item
                    if item_color:
                        v_specs.append(item_color)
                    elif variant.get("color"): # Fallback to first color in variant
                        colors = variant.get("color", [])
                        if isinstance(colors, list) and len(colors) > 0:
                             v_specs.append(colors[0].get("colorName", ""))

                    # Storage/Memory
                    if variant.get("memory"):
                        memory = variant.get("memory", {})
                        ram = variant.get("ram")
                        if isinstance(memory, dict) and memory.get("storage"):
                            v_specs.append(memory["storage"])
                        if isinstance(ram, dict) and ram.get("ram"):
                            v_specs.append(ram["ram"])
                    
                    if v_specs:
                        variant_name = " - ".join(v_specs)
                
                # 4. Product Name
                product_name = product.get("name", "Sản phẩm")
                if len(product_name) > 35:
                    product_name = product_name[:32] + "..."
                    
                quantity = item.get("quantity", 1)
                
                # 5. Price Logic
                price = item.get("price")
                if price is None:
                    if variant and variant.get("price"):
                        price = variant.get("price")
                    else:
                        price = product.get("price", 0)
                
                item_total = price * quantity
                true_total += item_total
                
                # 6. Image Logic
                image_url = ""
                
                # Try to get image from variant based on color
                if variant and variant.get("color"):
                    colors = variant.get("color", [])
                    target_color = item.get("color", "")
                    
                    # Find matching color
                    found_image = False
                    if target_color:
                        for color_obj in colors:
                            if color_obj.get("colorName", "").lower() == target_color.lower():
                                if color_obj.get("images") and len(color_obj["images"]) > 0:
                                    image_url = color_obj["images"][0]
                                    found_image = True
                                    break
                    
                    # Fallback to first color if no match or no target color
                    if not found_image and len(colors) > 0:
                         if colors[0].get("images") and len(colors[0]["images"]) > 0:
                            image_url = colors[0]["images"][0]

                # Fallback to product images
                if not image_url and product.get("images") and len(product["images"]) > 0:
                    first_image = product["images"][0]
                    if isinstance(first_image, dict):
                        image_url = first_image.get("url", "")
                    else:
                        image_url = first_image
                
                # Add item HTML
                cart_html_items += f"""
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; font-size: 13px;">
                    <div style="width: 45px; height: 45px; flex-shrink: 0; background: #f9fafb; border-radius: 6px; overflow: hidden; margin-right: 10px;">
                        <img src="{image_url}" style="width: 100%; height: 100%; object-fit: cover;" onerror="this.style.display='none'">
                    </div>
                    <div style="flex: 1; padding-right: 10px; min-width: 0;">
                        <div style="color: #374151; font-weight: 500; line-height: 1.4; word-wrap: break-word;">{product_name}</div>
                        {f'<div style="color: #9ca3af; font-size: 11px; margin-top: 2px;">{variant_name}</div>' if variant_name else ''}
                        <div style="color: #9ca3af; font-size: 12px; margin-top: 2px;">x{quantity}</div>
                    </div>
                    <div style="color: #111827; font-weight: 600; white-space: nowrap; flex-shrink: 0;">{price:,.0f}₫</div>
                </div>
                """
              
            except Exception as e:
                print(f"Error processing cart item: {e}")
                print(traceback.format_exc())
                continue

        # Build complete cart HTML card
        html = f"""
        <div style="
            border: 1px solid #e5e7eb; 
            border-radius: 6px; 
            padding: 16px; 
            margin: 8px 0;
            background: #ffffff;
            font-family: system-ui, -apple-system, sans-serif;
            max-width: 320px;
            min-width: 320px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        ">
            <!-- Header -->
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #f3f4f6;">
                <div style="font-size: 14px; font-weight: 700; color: #111827;">🛒 Giỏ hàng của bạn</div>
                <div style="font-size: 12px; color: #9ca3af;">{len(items)} sản phẩm</div>
            </div>
            
            <!-- Cart Items -->
            <div style="margin-bottom: 12px;">
                {cart_html_items}
            </div>
            
            <!-- Total -->
            <div style="padding-top: 12px; border-top: 1px solid #f3f4f6; display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                <div style="font-size: 13px; color: #6b7280;">Tổng tiền</div>
                <div style="font-size: 15px; font-weight: 700; color: #111827;">{true_total:,.0f}₫</div>
            </div>
            
            <!-- Action Button -->
            <a href="{os.getenv('FRONTEND_URL')}/cart" target="_blank" style="
                display: block;
                width: 100%;
                padding: 10px;
                background: #111827;
                color: #ffffff;
                text-align: center;
                text-decoration: none;
                font-size: 13px;
                font-weight: 500;
                border-radius: 6px;
                transition: background 0.2s;
            ">
                Xem chi tiết &amp; Thanh toán
            </a>
        </div>
        """
        
        dispatcher.utter_message(text=html)
        return []
