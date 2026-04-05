from pathlib import Path

folders = [
    "app",
    "app/templates",
    "app/static",
    "app/services",
    "uploads",
]

files = [
    "app/main.py",
    "app/database.py",
    "app/models.py",
    "app/auth.py",
    "app/services/ai_service.py",
    "app/templates/login.html",
    "app/templates/dashboard.html",
    "app/templates/result.html",
    "app/templates/history.html",
    "app/templates/admin.html",
    "app/static/style.css",
    ".env",
]

base = Path.cwd()

print("Çalışılan klasör:", base)

for folder in folders:
    path = base / folder
    path.mkdir(parents=True, exist_ok=True)
    print("Klasör oluşturuldu:", path)

for file in files:
    path = base / file
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")
    print("Dosya hazır:", path)

env_path = base / ".env"
env_path.write_text("SECRET_KEY=supersecretkey123\n", encoding="utf-8")

print("Tamamlandı.")