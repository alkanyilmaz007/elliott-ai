import os
import shutil
import uuid
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from pymongo.errors import DuplicateKeyError
from bson import ObjectId

from .database import users_collection
from .auth import hash_password, verify_password

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

app = FastAPI()

SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "change-this-in-render")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    https_only=False,
)

UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def parse_bool_checkbox(value: str | None) -> bool:
    return value is not None


def parse_date(value: str | None):
    if not value or not value.strip():
        return None
    try:
        parsed = datetime.strptime(value.strip(), "%Y-%m-%d")
        return parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def serialize_user(doc: dict | None):
    if not doc:
        return None
    doc = dict(doc)
    doc["id"] = str(doc["_id"])
    return doc


def get_user_by_id(user_id: str):
    try:
        return users_collection.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return None


def get_user_by_username(username: str):
    return users_collection.find_one({"username": username.strip()})


def list_users():
    return [serialize_user(u) for u in users_collection.find().sort("_id", -1)]


def get_current_user(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return serialize_user(get_user_by_id(user_id))


def require_admin(user: dict):
    if not user or user.get("role") != "super_admin":
        raise PermissionError("Bu işlem için admin yetkisi gerekiyor.")


def save_uploaded_file(upload: UploadFile | None, prefix: str) -> str:
    if not upload or not getattr(upload, "filename", ""):
        return ""

    ext = Path(upload.filename).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
        raise ValueError("Sadece görsel dosyaları yüklenebilir.")

    filename = f"{prefix}_{uuid.uuid4().hex}{ext}"
    full_path = UPLOAD_DIR / filename

    with open(full_path, "wb") as f:
        shutil.copyfileobj(upload.file, f)

    return str(full_path)


def delete_file_if_exists(path_str: str | None):
    if not path_str:
        return
    try:
        path = Path(path_str)
        if path.exists() and path.is_file():
            path.unlink()
    except Exception:
        pass


def replace_uploaded_file(upload: UploadFile | None, old_path: str | None, prefix: str) -> str:
    if not upload or not getattr(upload, "filename", ""):
        return old_path or ""

    new_path = save_uploaded_file(upload, prefix)

    if old_path and old_path != new_path:
        delete_file_if_exists(old_path)

    return new_path


@app.on_event("startup")
def startup_checks():
    ping_mongo()

    admin = users_collection.find_one({"username": "admin"})
    if admin:
        users_collection.update_one(
            {"_id": admin["_id"]},
            {
                "$set": {
                    "password_hash": hash_password("280980Evr."),
                    "role": "super_admin",
                    "company_name": admin.get("company_name") or "ADMIN",
                    "display_name": admin.get("display_name") or "ADMIN",
                    "is_active": True,
                    "can_send_analysis": True,
                    "can_send_signal": True,
                    "can_send_news": True,
                    "can_send_data_calendar": True,
                    "subscription_plan": "lifetime",
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        print("Admin güncellendi")
    else:
        users_collection.insert_one(
            {
                "username": "admin",
                "password_hash": hash_password("280980Evr."),
                "role": "super_admin",
                "company_name": "ADMIN",
                "display_name": "ADMIN",
                "logo_path": "",
                "frame_main_path": "",
                "frame_fractal_path": "",
                "frame_news_path": "",
                "frame_data_path": "",
                "telegram_bot_token": "",
                "telegram_chat_id": "",
                "is_active": True,
                "can_send_analysis": True,
                "can_send_signal": True,
                "can_send_news": True,
                "can_send_data_calendar": True,
                "subscription_plan": "lifetime",
                "subscription_end_date": None,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        )
        print("Admin oluşturuldu")


def render_login_page(error: str = "") -> HTMLResponse:
    error_html = f"<p style='color:#c62828'>{error}</p>" if error else ""
    return HTMLResponse(f"""
    <!doctype html>
    <html lang="tr">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Giriş</title>
    </head>
    <body style="font-family:Arial;max-width:520px;margin:40px auto;">
        <h1>Giriş</h1>
        {error_html}
        <form method="post" action="/login">
            <label>Kullanıcı Adı</label><br>
            <input type="text" name="username" required style="width:100%;padding:10px;"><br><br>

            <label>Şifre</label><br>
            <input type="password" name="password" required style="width:100%;padding:10px;"><br><br>

            <button type="submit">Giriş Yap</button>
        </form>
    </body>
    </html>
    """)


def render_dashboard(user: dict, users: list[dict] | None = None, error: str = "", success: str = ""):
    flash = ""
    if error:
        flash += f"<p style='color:#c62828'>{error}</p>"
    if success:
        flash += f"<p style='color:#2e7d32'>{success}</p>"

    if user.get("role") == "super_admin":
        rows = ""
        for u in users or []:
            if u["username"] == "admin":
                continue
            rows += f"""
            <tr>
                <td>{u['id']}</td>
                <td>{u.get('username', '')}</td>
                <td>{u.get('display_name', '')}</td>
                <td>{u.get('company_name', '')}</td>
                <td>{u.get('subscription_plan', '')}</td>
                <td>{"Aktif" if u.get("is_active") else "Pasif"}</td>
                <td>
                    <form method="post" action="/admin/users/{u['id']}/delete" style="display:inline;">
                        <button type="submit">Sil</button>
                    </form>
                </td>
            </tr>
            """

        return HTMLResponse(f"""
        <!doctype html>
        <html lang="tr">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Admin Panel</title>
        </head>
        <body style="font-family:Arial;max-width:1100px;margin:40px auto;">
            <h1>Admin Panel</h1>
            <p>Hoş geldin {user.get("display_name") or user.get("username")}</p>
            <p><a href="/logout">Çıkış</a></p>
            {flash}

            <hr>
            <h2>Yeni Kullanıcı Ekle</h2>
            <form method="post" action="/admin/users/create" enctype="multipart/form-data">
                <input name="username" placeholder="Kullanıcı adı" required style="width:100%;padding:10px;"><br><br>
                <input name="password" placeholder="Şifre" required style="width:100%;padding:10px;"><br><br>
                <input name="display_name" placeholder="Görünen ad" style="width:100%;padding:10px;"><br><br>
                <input name="company_name" placeholder="Şirket adı" style="width:100%;padding:10px;"><br><br>

                <select name="subscription_plan" style="width:100%;padding:10px;">
                    <option value="standard">standard</option>
                    <option value="pro">pro</option>
                    <option value="premium">premium</option>
                    <option value="lifetime">lifetime</option>
                </select><br><br>

                <input type="date" name="subscription_end_date" style="width:100%;padding:10px;"><br><br>
                <input name="telegram_bot_token" placeholder="Telegram bot token" style="width:100%;padding:10px;"><br><br>
                <input name="telegram_chat_id" placeholder="Telegram chat id" style="width:100%;padding:10px;"><br><br>

                <label><input type="checkbox" name="is_active" checked> Aktif</label><br>
                <label><input type="checkbox" name="can_send_analysis" checked> Analiz</label><br>
                <label><input type="checkbox" name="can_send_signal" checked> Sinyal</label><br>
                <label><input type="checkbox" name="can_send_news"> Haber</label><br>
                <label><input type="checkbox" name="can_send_data_calendar"> Veri Takvimi</label><br><br>

                <label>Logo</label><br>
                <input type="file" name="logo_file" accept="image/*"><br><br>

                <label>Main Frame</label><br>
                <input type="file" name="frame_main_file" accept="image/*"><br><br>

                <label>Fractal Frame</label><br>
                <input type="file" name="frame_fractal_file" accept="image/*"><br><br>

                <label>News Frame</label><br>
                <input type="file" name="frame_news_file" accept="image/*"><br><br>

                <label>Data Frame</label><br>
                <input type="file" name="frame_data_file" accept="image/*"><br><br>

                <button type="submit">Kullanıcıyı Kaydet</button>
            </form>

            <hr>
            <h2>Kullanıcılar</h2>
            <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%;">
                <tr>
                    <th>ID</th>
                    <th>Kullanıcı</th>
                    <th>Görünen Ad</th>
                    <th>Şirket</th>
                    <th>Plan</th>
                    <th>Durum</th>
                    <th>İşlem</th>
                </tr>
                {rows}
            </table>
        </body>
        </html>
        """)

    return HTMLResponse(f"""
    <!doctype html>
    <html lang="tr">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Kullanıcı Paneli</title>
    </head>
    <body style="font-family:Arial;max-width:800px;margin:40px auto;">
        <h1>Kullanıcı Paneli</h1>
        <p>Hoş geldin {user.get("display_name") or user.get("username")}</p>
        <p>Şirket: {user.get("company_name") or "-"}</p>
        <p>Plan: {user.get("subscription_plan") or "-"}</p>
        <p><a href="/logout">Çıkış</a></p>
        {flash}
    </body>
    </html>
    """)


@app.get("/ping")
def ping():
    return {"status": "ok", "mongo": "connected"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return render_login_page()


@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    user = get_user_by_username(username)

    if not user or not verify_password(password, user.get("password_hash", "")):
        return render_login_page("Kullanıcı adı veya şifre hatalı.")

    if not user.get("is_active", False):
        return render_login_page("Bu kullanıcı pasif durumda.")

    request.session["user_id"] = str(user["_id"])
    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    users = list_users() if user.get("role") == "super_admin" else None
    return render_dashboard(user=user, users=users)


@app.post("/admin/users/create", response_class=HTMLResponse)
def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    display_name: str = Form(""),
    company_name: str = Form(""),
    subscription_plan: str = Form("standard"),
    subscription_end_date: str = Form(""),
    telegram_bot_token: str = Form(""),
    telegram_chat_id: str = Form(""),
    is_active: str | None = Form(None),
    can_send_analysis: str | None = Form(None),
    can_send_signal: str | None = Form(None),
    can_send_news: str | None = Form(None),
    can_send_data_calendar: str | None = Form(None),
    logo_file: UploadFile | None = File(None),
    frame_main_file: UploadFile | None = File(None),
    frame_fractal_file: UploadFile | None = File(None),
    frame_news_file: UploadFile | None = File(None),
    frame_data_file: UploadFile | None = File(None),
):
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    try:
        require_admin(current_user)

        logo_path = save_uploaded_file(logo_file, "logo")
        frame_main_path = save_uploaded_file(frame_main_file, "frame_main")
        frame_fractal_path = save_uploaded_file(frame_fractal_file, "frame_fractal")
        frame_news_path = save_uploaded_file(frame_news_file, "frame_news")
        frame_data_path = save_uploaded_file(frame_data_file, "frame_data")

        users_collection.insert_one(
            {
                "username": username.strip(),
                "password_hash": hash_password(password.strip()),
                "role": "user",
                "company_name": company_name.strip(),
                "display_name": display_name.strip(),
                "logo_path": logo_path,
                "frame_main_path": frame_main_path,
                "frame_fractal_path": frame_fractal_path,
                "frame_news_path": frame_news_path,
                "frame_data_path": frame_data_path,
                "telegram_bot_token": telegram_bot_token.strip(),
                "telegram_chat_id": telegram_chat_id.strip(),
                "is_active": parse_bool_checkbox(is_active),
                "can_send_analysis": parse_bool_checkbox(can_send_analysis),
                "can_send_signal": parse_bool_checkbox(can_send_signal),
                "can_send_news": parse_bool_checkbox(can_send_news),
                "can_send_data_calendar": parse_bool_checkbox(can_send_data_calendar),
                "subscription_plan": subscription_plan.strip() or "standard",
                "subscription_end_date": parse_date(subscription_end_date),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        )

        return render_dashboard(current_user, list_users(), success="Kullanıcı başarıyla oluşturuldu.")

    except DuplicateKeyError:
        return render_dashboard(current_user, list_users(), error="Bu kullanıcı adı zaten kayıtlı.")
    except PermissionError as e:
        return HTMLResponse(str(e), status_code=403)
    except Exception as e:
        return render_dashboard(current_user, list_users(), error=f"Hata: {e}")


@app.post("/admin/users/{user_id}/delete", response_class=HTMLResponse)
def delete_user(user_id: str, request: Request):
    admin = get_current_user(request)
    if not admin:
        return RedirectResponse(url="/login", status_code=302)

    try:
        require_admin(admin)

        target_user = get_user_by_id(user_id)
        if not target_user or target_user.get("username") == "admin":
            return render_dashboard(admin, list_users(), error="Kullanıcı bulunamadı veya silinemez.")

        delete_file_if_exists(target_user.get("logo_path"))
        delete_file_if_exists(target_user.get("frame_main_path"))
        delete_file_if_exists(target_user.get("frame_fractal_path"))
        delete_file_if_exists(target_user.get("frame_news_path"))
        delete_file_if_exists(target_user.get("frame_data_path"))

        users_collection.delete_one({"_id": ObjectId(user_id)})

        return render_dashboard(admin, list_users(), success="Kullanıcı silindi.")

    except PermissionError as e:
        return HTMLResponse(str(e), status_code=403)
    except Exception as e:
        return render_dashboard(admin, list_users(), error=f"Hata: {e}")
