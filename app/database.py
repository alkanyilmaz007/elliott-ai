import os
from pymongo import MongoClient
from bson.objectid import ObjectId

# Render Environment Variable olarak DATABASE_URL eklemelisin
# Örnek DATABASE_URL:
# mongodb+srv://kullanici:sifre@cluster0.mongodb.net/elliott_saas_v3?retryWrites=true&w=majority
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set!")

# MongoDB client ve DB bağlantısı
client = MongoClient(DATABASE_URL)
db = client.get_default_database()  # DATABASE_URL'deki db ismini alır

# Kullanıcı tablosu yerine collection kullanıyoruz
users_collection = db["users"]

# Helper fonksiyonlar
def create_user(username: str, password_hash: str, is_admin=False):
    """Yeni kullanıcı oluşturur"""
    user = {
        "username": username,
        "password_hash": password_hash,
        "is_admin": is_admin,
    }
    result = users_collection.insert_one(user)
    return str(result.inserted_id)

def get_user_by_username(username: str):
    """Kullanıcıyı username ile bulur"""
    return users_collection.find_one({"username": username})

def delete_user(user_id: str):
    """Kullanıcıyı siler"""
    return users_collection.delete_one({"_id": ObjectId(user_id)})

def update_user(user_id: str, update_data: dict):
    """Kullanıcıyı günceller"""
    return users_collection.update_one({"_id": ObjectId(user_id)}, {"$set": update_data})
