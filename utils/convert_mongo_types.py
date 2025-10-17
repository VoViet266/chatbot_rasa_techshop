from bson import ObjectId
from datetime import datetime

def convert_mongo_types(obj):
    if isinstance(obj, list):
        return [convert_mongo_types(item) for item in obj]
    if isinstance(obj, dict):
        return {key: convert_mongo_types(value) for key, value in obj.items()}
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj