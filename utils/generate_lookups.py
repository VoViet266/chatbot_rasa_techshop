import yaml
from pymongo import MongoClient

# --- Lớp này sẽ "dạy" PyYAML cách in chuỗi nhiều dòng bằng | ---
class LiteralString(str):
    pass

def literal_string_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')

# Đăng ký lớp này với thư viện yaml
yaml.add_representer(LiteralString, literal_string_representer)
# ------------------------------------------------------------------

# Kết nối DB
client = MongoClient("mongodb+srv://VieDev:durNBv9YO1TvPvtJ@cluster0.h4trl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
database = client["techshop_db"]

print("Đang kết nối database và lấy dữ liệu...")

# 1. Lấy Products
products_model = database["products"]
product_names = products_model.distinct("name")
# Lọc bỏ dữ liệu rác (nếu có)
product_names = [name for name in product_names if name and "test" not in name.lower() and "đen như" not in name.lower()]

# 2. Lấy Brands
brands_model = database["brands"]
brand_names = brands_model.distinct("name")

# 3. Lấy Categories
categories_model = database["categories"]
category_names = categories_model.distinct("name")

print(f"Đã lấy {len(product_names)} sản phẩm, {len(brand_names)} thương hiệu, {len(category_names)} danh mục.")

# --- TẠO CHUỖI VÍ DỤ ---
# Quan trọng: Tạo chuỗi trước với dấu gạch ngang và xuống dòng
product_examples = "\n".join([f"- {name}" for name in product_names])
brand_examples = "\n".join([f"- {name}" for name in brand_names])
category_examples = "\n".join([f"- {name}" for name in category_names])

# 4. Tạo nội dung cho file NLU
nlu_data = {
    "version": "3.1",
    "nlu": [
        {
            "lookup": "product_name",
            "examples": LiteralString(product_examples)
        },
        {
            "lookup": "brand",
            "examples": LiteralString(brand_examples)
        },
        {
            "lookup": "category",
            "examples": LiteralString(category_examples)
        }
    ]
}

# 5. Ghi file
output_file_path = "data/nlu/lookups.yml" 

with open(output_file_path, 'w', encoding='utf-8') as f:
    # Dùng Dumper=yaml.Dumper để giữ thứ tự (quan trọng!)
    yaml.dump(nlu_data, f, allow_unicode=True, sort_keys=False, Dumper=yaml.Dumper)

client.close()