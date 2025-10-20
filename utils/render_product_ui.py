from utils.format_currentcy import format_vnd
import re

def render_ui(variants):
    result = f"<span>Dưới đây là một số sản phẩm phù hợp với nhu cầu của bạn</span>"
    if len(variants) != 0:
      for variant in variants:
          result += f"""<div id="product-template" role="group" aria-label="Sản phẩm" 
    style="display:flex;justify-content:flex-start;align-items:flex-start;box-sizing:border-box;
          padding:0;margin:0;gap:8px;max-width:520px;border-radius:6px;font-family:Arial,Helvetica,sans-serif; border: 1px solid #ececec; padding: 8px;">

    <!-- Ảnh sản phẩm -->
    <div dir="ltr" 
      style="display:flex;flex-direction:column;justify-content:flex-start;align-items:center;flex:0 0 auto;
            padding:0;margin:0;">
      <img src="{variant["color"][0]["images"][0]}" alt="[Tên sản phẩm]" 
          style="width:80px;height:70px;object-fit:contain;object-position:center;">
    </div>

    <!-- Nội dung sản phẩm -->
    <div dir="ltr" 
      style="display:flex;flex-direction:column;justify-content:flex-start;flex:1 1 50px;
            padding:0;margin:0;min-width:0;">

      <!-- Tên sản phẩm -->
      <p aria-hidden="false" 
        style="font-size:12px;color:#101519;line-height:1.33;margin:0 0 4px 0;overflow-wrap:break-word;">
        {variant["name"]}
      </p>

      <!-- Giá tiền hiện tại -->
      <p aria-live="polite" 
        style="font-size:14px;color:#dc2626;font-weight:600;white-space:nowrap;text-overflow:ellipsis;
                overflow:hidden;margin:0 0 6px 0;line-height:1.33;">
        { format_vnd(variant["price"] * (1 - variant.get('discount', 0)/100)) }
      </p>

      <!-- Giá gốc và giảm giá -->
      <div aria-hidden="true" 
          style="display:flex;align-items:center;gap:4px;margin-bottom:6px;">
        <span style="font-size:12px;color:#767676;text-decoration:line-through;line-height:1.33;">
          {format_vnd(variant["price"])}
        </span>
        <span style="font-size:12px;color:red;line-height:1.33;">
          {variant.get('discount', 0)}%
        </span>
      </div>

      <!-- RAM và bộ nhớ trong -->
      <div aria-hidden="true" 
          style="display:flex;align-items:center;gap:4px;margin-bottom:6px;">
        <span style="font-size:12px;color:#767676;line-height:1.33;">
          RAM {variant['memory']['ram']}
        </span>
        <span style="font-size:12px;color:red;line-height:1.33;">
          Bộ nhớ trong {variant['memory']['storage']}
        </span>
      </div>

      <!-- Dung lượng pin -->
      <div aria-hidden="true" 
          style="display:flex;align-items:center;gap:4px;margin-bottom:6px;">
        <span style="font-size:12px;color:#767676;line-height:1.33;">
          Pin {variant.get('battery', 'Không rõ')}
        </span>
      </div>

      <!-- Nút hành động -->
      <div role="toolbar" aria-label="Hành động" 
          style="display:flex;gap:4px;margin-top:4px;">
          <a href="http://localhost:5173/product/{variant['product_id']}">
            <button type="button" tabindex="0" role="button"
              style="display:inline-flex;align-items:center;justify-content:center;padding:6px 8px;
                    font-size:12px;color:#101519;background:transparent;border:none;cursor:pointer;
                    border-radius:4px;user-select:none;">
              Chọn mua
            </button>
          </a>
      </div>
    </div>
  </div>"""
      cleaned_result = re.sub(r'\s+', ' ', result).strip()
      return cleaned_result
    else:
        return "Không có biến thể cho sản phẩm này!"