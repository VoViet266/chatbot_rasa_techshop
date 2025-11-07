
from pymongo import MongoClient

class DatabaseService:
    """Service để kết nối và truy vấn MongoDB"""
    
    def __init__(self):
        self.client = MongoClient("mongodb+srv://VieDev:durNBv9YO1TvPvtJ@cluster0.h4trl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
        self.db = self.client["techshop_db"]
        self.users_collection = self.db["users"]
        self.orders_collection = self.db["orders"]
        self.carts_collection = self.db["carts"]
        self.products_collection = self.db["products"]
        self.variants_collection = self.db["variants"]
        self.brands_collection = self.db["brands"]
        self.categories_collection = self.db["categories"]
        self.inventories_collection = self.db["inventories"]
        self.branches_collection = self.db["branches"]