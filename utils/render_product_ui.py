from utils.format_currentcy import format_vnd
import re

def render_ui(variants):
    if not variants:
        return "Không có sản phẩm phù hợp với nhu cầu của bạn."
    
    result = '<div style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Arial,sans-serif;color:#1a1a1a;"><p style="margin:0 0 16px;font-size:14px;font-weight:500;">Dưới đây là một số sản phẩm phù hợp với nhu cầu của bạn</p>'
    
    for variant in variants:
        discount = variant.get('discount', 0)
        discounted_price = variant["price"] * (1 - discount/100)
        
        result += f'''<div style="display:flex;gap:12px;padding:12px;margin-bottom:12px;background:#fff;border:1px solid #e5e5e5;border-radius:8px;transition:box-shadow 0.2s;">
    <img src="{variant["color"][0]["images"][0]}" alt="{variant["name"]}" style="width:90px;height:90px;object-fit:contain;flex-shrink:0;border-radius:4px;">
    <div style="flex:1;min-width:0;">
        <h3 style="margin:0 0 8px;font-size:14px;font-weight:500;line-height:1.4;color:#1a1a1a;">{variant["name"]}</h3>
        <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px;">
            <span style="font-size:16px;font-weight:600;color:#d32f2f;">{format_vnd(discounted_price)}</span>
            {f'<span style="font-size:13px;color:#9e9e9e;text-decoration:line-through;">{format_vnd(variant["price"])}</span>' if discount > 0 else ''}
            {f'<span style="font-size:12px;color:#d32f2f;font-weight:500;">-{discount}%</span>' if discount > 0 else ''}
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px;">
            <span style="font-size:12px;padding:4px 8px;background:#f5f5f5;border-radius:4px;color:#616161;">RAM {variant['memory']['ram']}</span>
            <span style="font-size:12px;padding:4px 8px;background:#f5f5f5;border-radius:4px;color:#616161;">ROM {variant['memory']['storage']}</span>
            <span style="font-size:12px;padding:4px 8px;background:#f5f5f5;border-radius:4px;color:#616161;">Pin {variant.get('battery', 'N/A')}</span>
        </div>
        <a href="http://localhost:5173/product/{variant['product_id']}" style="display:inline-block;padding:8px 16px;font-size:13px;font-weight:500;color:#fff;background:#1976d2;border-radius:6px;text-decoration:none;transition:background 0.2s;">Xem chi tiết</a>
    </div>
</div>'''
    
    result += '</div>'
    cleaned_result = re.sub(r'\s+', ' ', result).strip()
    return cleaned_result