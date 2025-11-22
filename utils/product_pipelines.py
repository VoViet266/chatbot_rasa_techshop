# db/pipelines/product_pipelines.py
def build_search_pipeline(product_name, limit = 1):
    return [
        {
            "$search": {
                "index": "tech_ai_search",
                "text": {
                    "query": product_name,
                    "path": "name",
                    "fuzzy": {"maxEdits": 2, "prefixLength": 2}
                }
            }
        },
        {
            "$lookup": {
                "from": "brands",
                "localField": "brand",
                "foreignField": "_id",
                "as": "brand_info"
            }
        },
        {
            "$unwind": {
                "path": "$brand_info",
                "preserveNullAndEmptyArrays": True
            }
        },
        {
            "$lookup": {
                "from": "categories",
                "localField": "category",
                "foreignField": "_id",
                "as": "category_info"
            }
        },
        {
            "$unwind": {
                "path": "$category_info",
                "preserveNullAndEmptyArrays": True
            }
        },
        {
            "$project": {
                "name": 1,
                "brand": {
                    "_id": "$brand_info._id",
                    "name": "$brand_info.name"
                },
                "category": {
                    "_id": "$category_info._id",
                    "name": "$category_info.name",
                    "configFields": "$category_info.configFields"
                },
                "discount": 1,
                "variants": 1,
                "attributes": 1,
                "specifications": 1
            }
        },
        {"$limit": limit}
    ]
