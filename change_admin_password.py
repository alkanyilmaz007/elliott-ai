from app.database import SessionLocal
from app.models import User
from app.auth import hash_password

print("Script başladı")

db = SessionLocal()
print("DB bağlantısı açıldı")

admin = db.query(User).filter(User.username == "admin").first()
print("Admin sorgusu tamamlandı")

if admin:
    print("Admin bulundu")
    admin.password_hash = hash_password("280980Evren+")
    db.commit()
    print("Admin şifresi güncellendi")
else:
    print("Admin bulunamadı")

db.close()
print("Script bitti")