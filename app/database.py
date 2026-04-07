import os
from pymongo import MongoClient
from bson.objectid import ObjectId
from urllib.parse import urlparse

parsed = urlparse(DATABASE_URL)
print("Mongo host:", parsed.hostname)
print("Mongo db:", parsed.path)
print("Mongo user:", parsed.username)

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set!")

# Daha net debug ve timeout için
print("DATABASE_URL raw:", repr(DATABASE_URL))
print("starts with mongodb:", str(DATABASE_URL).startswith("mongodb"))
client = MongoClient(DATABASE_URL, serverSelectionTimeoutMS=10000)

# DB adı connection string içinden alınır
db = client.get_default_database()
users_collection = db["users"]

def create_user(username: str, password_hash: str, is_admin=False):
    user = {
        "username": username,
        "password_hash": password_hash,
        "is_admin": is_admin,
    }
    result = users_collection.insert_one(user)
    return str(result.inserted_id)

def get_user_by_username(username: str):
    return users_collection.find_one({"username": username})

def delete_user(user_id: str):
    return users_collection.delete_one({"_id": ObjectId(user_id)})

def update_user(user_id: str, update_data: dict):
    return users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_data}
    )
