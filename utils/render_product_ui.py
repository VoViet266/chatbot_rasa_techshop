from utils.format_currentcy import format_vnd
import re


def render_variants_list(variants):
    if not variants:
        return "Không có sản phẩm phù hợp với nhu cầu của bạn."
    
    result = '<div style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Arial,sans-serif;color:#1a1a1a;"><p style="margin:0 0 16px;font-size:14px;font-weight:500;">Dưới đây là một số sản phẩm phù hợp với nhu cầu của bạn</p>'
    
    for variant in variants:
        discount = variant.get('discount', 0)
        price = variant.get("price", 0)
        discounted_price = price * (1 - discount/100)
        
        # Construct display name
        product_name = variant.get("name", "Sản phẩm")
        ram = variant.get('memory', {}).get('ram', '')
        storage = variant.get('memory', {}).get('storage', '')
        if ram or storage:
            display_name = f"{product_name} ({ram}/{storage})"
        else:
            display_name = product_name

        try:
            image_url = variant["color"][0]["images"][0]
        except (KeyError, IndexError, TypeError):
            image_url = "https://via.placeholder.com/90"

        sold_count = variant.get('soldCount', 0)
        rating = variant.get('averageRating', 0)

        result += f'''<div style="display:flex;gap:12px;padding:12px;margin-bottom:12px;background:#fff;border:1px solid #e5e5e5;border-radius:8px;transition:box-shadow 0.2s;">
    <img src="{image_url}" alt="{display_name}" style="width:90px;height:90px;object-fit:contain;flex-shrink:0;border-radius:4px;">
    <div style="flex:1;min-width:0;">
        <h3 style="margin:0 0 8px;font-size:14px;font-weight:500;line-height:1.4;color:#1a1a1a;">{display_name}</h3>
        <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px;">
            <span style="font-size:16px;font-weight:600;color:#d32f2f;">{format_vnd(discounted_price)}</span>
            {f'<span style="font-size:13px;color:#9e9e9e;text-decoration:line-through;">{format_vnd(price)}</span>' if discount > 0 else ''}
            {f'<span style="font-size:12px;color:#d32f2f;font-weight:500;">-{discount}%</span>' if discount > 0 else ''}
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px;">
            <span style="font-size:12px;padding:4px 8px;background:#f5f5f5;border-radius:4px;color:#616161;">RAM {variant.get('memory', {}).get('ram', 'N/A')}</span>
            <span style="font-size:12px;padding:4px 8px;background:#f5f5f5;border-radius:4px;color:#616161;">ROM {variant.get('memory', {}).get('storage', 'N/A')}</span>
            <span style="font-size:12px;padding:4px 8px;background:#f5f5f5;border-radius:4px;color:#616161;">Pin {variant.get('battery', 'N/A')}</span>
            <span style="font-size:12px;padding:4px 8px;background:#f5f5f5;border-radius:4px;color:#616161;">Đã bán: {sold_count}</span>
            <span style="font-size:12px;padding:4px 8px;background:#f5f5f5;border-radius:4px;color:#616161;">⭐ {rating}</span>
        </div>
        <a href="http://localhost:5173/product/{variant.get('product_id', '')}" style="display:inline-block;padding:8px 16px;font-size:13px;font-weight:500;color:#fff;background:#1976d2;border-radius:6px;text-decoration:none;transition:background 0.2s;">Xem chi tiết</a>
    </div>
</div>'''
    
    result += '</div>'
    cleaned_result = re.sub(r'\s+', ' ', result).strip()
    return cleaned_result

def render_products(products):
    if not products:
        return "Không có sản phẩm phù hợp với nhu cầu của bạn."
    
    result = '<div style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Arial,sans-serif;color:#1a1a1a;"><p style="margin:0 0 16px;font-size:14px;font-weight:500;">Dưới đây là một số sản phẩm phù hợp với nhu cầu của bạn</p>'
    
    for product in products:
        # Extract variants and calculate price range
        variants = product.get('variants', [])
        prices = [v.get('price') for v in variants if v.get('price') is not None and v.get('price') > 0]
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0
        discount = product.get('discount', 0)
        
        # Price display logic
        if not prices:
            price_html = '<span style="font-size:14px;color:#616161;">Chưa có thông tin giá</span>'
        elif discount > 0:
            min_final = min_price * (1 - discount / 100)
            max_final = max_price * (1 - discount / 100)
            if min_price == max_price:
                price_html = f'''<span style="font-size:16px;font-weight:600;color:#d32f2f;">{format_vnd(min_final)}</span>
                                <span style="font-size:13px;color:#9e9e9e;text-decoration:line-through;">{format_vnd(min_price)}</span>'''
            else:
                price_html = f'''<span style="font-size:16px;font-weight:600;color:#d32f2f;">{format_vnd(min_final)} - {format_vnd(max_final)}</span>
                                <span style="font-size:13px;color:#9e9e9e;text-decoration:line-through;margin-left:8px;">{format_vnd(min_price)} - {format_vnd(max_price)}</span>'''
        else:
            if min_price == max_price:
                price_html = f'<span style="font-size:16px;font-weight:600;color:#d32f2f;">{format_vnd(min_price)}</span>'
            else:
                price_html = f'<span style="font-size:16px;font-weight:600;color:#d32f2f;">{format_vnd(min_price)} - {format_vnd(max_price)}</span>'

        # Image
        try:
            image_url = variants[0].get("color", [{}])[0].get("images", ["https://via.placeholder.com/90"])[0]
        except (IndexError, TypeError):
            image_url = "https://via.placeholder.com/90"

        # Other details
        sold_count = product.get('soldCount', 0)
        rating = product.get('averageRating', 0)
        product_id = product.get('_id', '')
        product_name = product.get('name', 'Sản phẩm')

        result += f'''<div style="display:flex;gap:12px;padding:12px;margin-bottom:12px;background:#fff;border:1px solid #e5e5e5;border-radius:8px;transition:box-shadow 0.2s;">
    <img src="{image_url}" alt="{product_name}" style="width:90px;height:90px;object-fit:contain;flex-shrink:0;border-radius:4px;">
    <div style="flex:1;min-width:0;">
        <h3 style="margin:0 0 8px;font-size:14px;font-weight:500;line-height:1.4;color:#1a1a1a;">{product_name}</h3>
        <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px;flex-wrap:wrap;">
            {price_html}
            {f'<span style="font-size:12px;color:#d32f2f;font-weight:500;">-{discount}%</span>' if discount > 0 else ''}
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px;">
            <span style="font-size:12px;padding:4px 8px;background:#f5f5f5;border-radius:4px;color:#616161;">Đã bán: {sold_count}</span>
            <span style="font-size:12px;padding:4px 8px;background:#f5f5f5;border-radius:4px;color:#616161;">⭐ {rating}</span>
        </div>
        <a href="http://localhost:5173/product/{product_id}" style="display:inline-block;padding:8px 16px;font-size:13px;font-weight:500;color:#fff;background:#1976d2;border-radius:6px;text-decoration:none;transition:background 0.2s;">Xem chi tiết</a>
    </div>
</div>'''
    
    result += '</div>'
    cleaned_result = re.sub(r'\s+', ' ', result).strip()
    return cleaned_result


def render_product_card(product, variants):
    if not variants:
        image_url = "https://via.placeholder.com/90" 
        price_html = '<span style="font-size:14px;color:#616161;">Chưa có thông tin giá</span>'
    else:
        try:
            image_url = variants[0].get("color", [{}])[0].get("images", ["https://via.placeholder.com/90"])[0]
        except (IndexError, TypeError):
            image_url = "https://via.placeholder.com/90"

        prices = [v.get('price') for v in variants if v.get('price') is not None and v.get('price') > 0]
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0
        discount = product.get('discount', 0) 

        if not prices:
            price_html = '<span style="font-size:14px;color:#616161;">Chưa có thông tin giá</span>'
        elif discount > 0:
            min_final = min_price * (1 - discount / 100)
            max_final = max_price * (1 - discount / 100)
            if min_price == max_price:
                price_html = f'''<span style="font-size:16px;font-weight:600;color:#d32f2f;">{format_vnd(min_final)}</span>
                                <span style="font-size:13px;color:#9e9e9e;text-decoration:line-through;">{format_vnd(min_price)}</span>'''
            else:
                price_html = f'''<span style="font-size:16px;font-weight:600;color:#d32f2f;">{format_vnd(min_final)} - {format_vnd(max_final)}</span>
                                <span style="font-size:13px;color:#9e9e9e;text-decoration:line-through;margin-left:8px;">{format_vnd(min_price)} - {format_vnd(max_price)}</span>'''
        else:
            if min_price == max_price:
                price_html = f'<span style="font-size:16px;font-weight:600;color:#d32f2f;">{format_vnd(min_price)}</span>'
            else:
                price_html = f'<span style="font-size:16px;font-weight:600;color:#d32f2f;">{format_vnd(min_price)} - {format_vnd(max_price)}</span>'
    
    variants_html_list = ""
    if variants:
        variants_html_list += '<div style="margin-top:12px;border-top:1px solid #eee;padding-top:12px;">'
        variants_html_list += f'<h4 style="margin:0 0 8px;font-size:13px;font-weight:500;color:#1a1a1a;">Các phiên bản ({len(variants)}):</h4>'
        
        product_discount = product.get('discount', 0)
        
        for v in variants:
            # Construct variant name from specs if name is missing
            variant_name = v.get("name")
            if not variant_name:
                ram = v.get('memory', {}).get('ram', '')
                storage = v.get('memory', {}).get('storage', '')
                if ram or storage:
                    variant_name = f"{ram} - {storage}"
                else:
                    variant_name = "Phiên bản tiêu chuẩn"

            price = v.get('price', 0)
            final_price = price * (1 - product_discount / 100)
            
            price_display_html = f'<span style="font-size:13px;font-weight:500;color:#d32f2f;">{format_vnd(final_price)}</span>'
            if product_discount > 0:
                price_display_html += f'<span style="font-size:12px;color:#9e9e9e;text-decoration:line-through;margin-left:5px;">{format_vnd(price)}</span>'
 
            variants_html_list += f'''
<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #f5f5f5;">
    <span style="font-size:13px;color:#333;padding-right:10px;">{variant_name}</span>
    <div style="flex-shrink:0;text-align:right;">{price_display_html}</div>
</div>
'''
        
        variants_html_list += '</div>'

    product_url = f"http://localhost:5173/product/{str(product.get('_id', ''))}"

    card_html = f'''<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;color:#1a1a1a;max-width:400px;">
<p style="margin:0 0 16px;font-size:14px;font-weight:500;">Đây là sản phẩm bạn tìm: {product["name"]}</p>

<a href="{product_url}" style="display:block; text-decoration:none; color:inherit;">
<div style="padding:12px;margin-bottom:12px;background:#fff;border:1px solid #e5e5e5;border-radius:8px;">
    
    <div style="display:flex;gap:12px;">
        <img src="{image_url}" alt="{product["name"]}" style="width:90px;height:90px;object-fit:contain;flex-shrink:0;border-radius:4px;">
        <div style="flex:1;min-width:0;">
            <h3 style="margin:0 0 8px;font-size:15px;font-weight:600;line-height:1.4;color:#1a1a1a;">{product["name"]}</h3>
            <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px;flex-wrap:wrap;">
                {price_html}
                {f'<span style="font-size:12px;color:#d32f2f;font-weight:500;padding:3px 6px;border:1px solid #fde0e0;border-radius:4px;background:#fff8f8;">-{discount}%</span>' if discount > 0 else ''}
            </div>
            <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px;">
                <span style="font-size:12px;padding:4px 8px;background:#f5f5f5;border-radius:4px;color:#616161;">Thương hiệu: {product.get('brand', {}).get('name', 'N/A')}</span>
                <span style="font-size:12px;padding:4px 8px;background:#f5f5f5;border-radius:4px;color:#616161;">Loại: {product.get('category', {}).get('name', 'N/A')}</span>
                <span style="font-size:12px;padding:4px 8px;background:#f5f5f5;border-radius:4px;color:#616161;">Đã bán: {product.get('soldCount', 0)}</span>
                <span style="font-size:12px;padding:4px 8px;background:#f5f5f5;border-radius:4px;color:#616161;">⭐ {product.get('averageRating', 0)}</span>
            </div>
        </div>
    </div>
    
    {variants_html_list}

</div>
</a> </div>'''
    cleaned_result = re.sub(r'\s+', ' ', card_html).strip()
    return cleaned_result