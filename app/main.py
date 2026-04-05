import os
import shutil
import uuid
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from .database import Base, engine, get_db
from .models import User
from .auth import hash_password, verify_password
from .services.ai_engine import run_full_analysis
from .services.telegram_service import (
    send_analysis_bundle,
    send_news_bundle,
    send_data_bundle,
)

app = FastAPI()

SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "super-secret-key")

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    https_only=False,
)

Base.metadata.create_all(bind=engine)

UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
def create_admin():
    db = next(get_db())
    try:
        user = db.query(User).filter(User.username == "admin").first()
        if not user:
            db.add(
                User(
                    username="admin",
                    password_hash=hash_password("123456"),
                    role="super_admin",
                    company_name="ADMIN",
                    display_name="ADMIN",
                    is_active=True,
                    can_send_analysis=True,
                    can_send_signal=True,
                    can_send_news=True,
                    can_send_data_calendar=True,
                    subscription_plan="lifetime",
                )
            )
            db.commit()
    finally:
        db.close()


def get_current_user(request: Request, db: Session):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


def get_user_or_none(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()


def require_admin(user: User):
    if not user or user.role != "super_admin":
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


def footer_for_user(user: User) -> str:
    return user.display_name or user.company_name or user.username


def get_content_frame_path(user: User, card_type: str) -> str:
    if card_type == "news":
        return user.frame_news_path or ""
    if card_type == "data":
        return user.frame_data_path or ""
    raise ValueError("Geçersiz kart tipi.")


def card_type_label(card_type: str) -> str:
    return "Haber" if card_type == "news" else "Veri"


def render_login_page(error: str = "") -> HTMLResponse:
    error_html = ""
    if error:
        error_html = f"""
        <div style="
            margin-bottom:16px;
            padding:14px 16px;
            border-radius:14px;
            background: rgba(255,95,122,0.12);
            border: 1px solid rgba(255,95,122,0.22);
            color:#ffb7c4;
        ">{error}</div>
        """

    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Elliott AI | Giriş</title>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                min-height: 100vh;
                font-family: Arial, sans-serif;
                color: white;
                background:
                    radial-gradient(circle at top left, rgba(79,124,255,0.20), transparent 30%),
                    radial-gradient(circle at top right, rgba(109,94,252,0.18), transparent 28%),
                    linear-gradient(180deg, #07101c 0%, #0b1424 100%);
            }}
            .wrapper {{
                min-height: 100vh;
                display: grid;
                grid-template-columns: 1.1fr 0.9fr;
                gap: 30px;
                padding: 40px;
                align-items: center;
            }}
            .left h1 {{
                font-size: 54px;
                line-height: 1.05;
                margin: 0 0 16px;
            }}
            .left p {{
                color: #aebedf;
                font-size: 18px;
                line-height: 1.7;
                max-width: 640px;
            }}
            .badge {{
                display: inline-block;
                padding: 8px 12px;
                border-radius: 999px;
                background: rgba(79,124,255,0.12);
                border: 1px solid rgba(79,124,255,0.28);
                color: #bdd0ff;
                font-size: 12px;
                letter-spacing: 1px;
                text-transform: uppercase;
                margin-bottom: 18px;
            }}
            .right {{
                display: flex;
                justify-content: center;
            }}
            .card {{
                width: 100%;
                max-width: 460px;
                background: rgba(18,28,49,0.72);
                border: 1px solid rgba(255,255,255,0.08);
                box-shadow: 0 20px 60px rgba(0,0,0,0.35);
                border-radius: 28px;
                padding: 34px;
            }}
            .logo {{
                width: 68px;
                height: 68px;
                border-radius: 50%;
                display: grid;
                place-items: center;
                font-weight: 700;
                font-size: 24px;
                background: linear-gradient(135deg, #4f7cff, #6d5efc);
                box-shadow: 0 10px 30px rgba(79,124,255,0.35);
                margin-bottom: 16px;
            }}
            .card h2 {{
                margin: 0 0 8px;
                font-size: 30px;
            }}
            .muted {{
                color: #9eb0cc;
                margin-bottom: 22px;
            }}
            label {{
                display: block;
                font-size: 14px;
                color: #dbe7ff;
                margin-bottom: 6px;
                margin-top: 12px;
            }}
            input {{
                width: 100%;
                padding: 14px 16px;
                border-radius: 14px;
                border: 1px solid rgba(255,255,255,0.08);
                outline: none;
                background: rgba(8,16,31,0.85);
                color: white;
                font-size: 15px;
            }}
            button {{
                width: 100%;
                margin-top: 18px;
                padding: 14px 18px;
                border-radius: 14px;
                border: none;
                cursor: pointer;
                font-weight: 700;
                color: white;
                background: linear-gradient(135deg, #4f7cff, #6d5efc);
                box-shadow: 0 10px 24px rgba(79,124,255,0.28);
            }}
            .note {{
                margin-top: 18px;
                color: #93a6c7;
                font-size: 13px;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="wrapper">
            <div class="left">
                <div class="badge">AI SIGNAL ENGINE</div>
                <h1>Elliott AI Platform</h1>
                <p>
                    Kullanıcı bazlı analiz üretimi, branded Telegram gönderimi ve admin kontrollü dağıtım altyapısı.
                </p>
            </div>

            <div class="right">
                <div class="card">
                    <div class="logo">EA</div>
                    <h2>Panele Giriş Yap</h2>
                    <div class="muted">Yetkili hesap bilgilerin ile devam et</div>

                    {error_html}

                    <form method="post" action="/login">
                        <label>Kullanıcı Adı</label>
                        <input type="text" name="username" placeholder="Kullanıcı adın" required>

                        <label>Şifre</label>
                        <input type="password" name="password" placeholder="Şifren" required>

                        <button type="submit">Giriş Yap</button>
                    </form>

                    <div class="note">Admin giriş: admin / 123456</div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """)


def _shared_styles() -> str:
    return """
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            color: white;
            background:
                radial-gradient(circle at top left, rgba(79,124,255,0.18), transparent 30%),
                radial-gradient(circle at top right, rgba(109,94,252,0.16), transparent 28%),
                linear-gradient(180deg, #07101c 0%, #0b1424 100%);
        }
        .wrap {
            max-width: 1450px;
            margin: 30px auto;
            padding: 0 20px 40px;
        }
        .top {
            background: rgba(18,28,49,0.72);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 24px;
            padding: 24px;
            margin-bottom: 20px;
            display:flex;
            justify-content:space-between;
            align-items:center;
        }
        .grid {
            display:grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 18px;
            margin-bottom: 20px;
        }
        .card {
            background: rgba(18,28,49,0.72);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 24px;
            padding: 24px;
        }
        .form-card {
            background: rgba(18,28,49,0.72);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 24px;
            padding: 24px;
            margin-bottom: 20px;
        }
        .form-card h2 { margin-top: 10px; }
        .top-fields {
            display:grid;
            grid-template-columns: 1fr 1fr;
            gap:16px;
            margin-bottom:18px;
        }
        .form-grid {
            display:grid;
            grid-template-columns: 1fr 1fr;
            gap:20px;
        }
        .image-card {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 22px;
            padding: 18px;
        }
        .preview-box {
            height: 250px;
            border-radius: 18px;
            background: rgba(255,255,255,0.04);
            border: 1px dashed rgba(255,255,255,0.12);
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 16px;
            position: relative;
        }
        .preview-box img {
            width: 100%;
            height: 100%;
            object-fit: contain;
            display: none;
        }
        .preview-placeholder {
            color: #8fa4c6;
            font-size: 14px;
            text-align: center;
            padding: 20px;
            line-height: 1.6;
        }
        .selection-grid {
            display:grid;
            grid-template-columns: 1fr 1fr;
            gap:14px;
            margin-top:12px;
        }
        .field { margin-bottom: 14px; }
        label {
            display:block;
            font-size:14px;
            margin-bottom:6px;
            color:#dbe7ff;
        }
        input, select, textarea {
            width:100%;
            padding:14px 16px;
            border-radius:14px;
            border:1px solid rgba(255,255,255,0.08);
            background: rgba(8,16,31,0.85);
            color:white;
            outline:none;
            font-family: Arial, sans-serif;
            font-size: 15px;
        }
        textarea {
            min-height: 180px;
            resize: vertical;
        }
        .checkline {
            display:flex;
            gap:10px;
            align-items:center;
            margin-top:10px;
            color:#dbe7ff;
            font-size:14px;
        }
        button {
            width:100%;
            margin-top:18px;
            padding:14px 18px;
            border-radius:14px;
            border:none;
            cursor:pointer;
            font-weight:700;
            color:white;
            background: linear-gradient(135deg, #4f7cff, #6d5efc);
        }
        .tiny {
            display:inline-block;
            padding:8px 12px;
            border-radius:999px;
            background: rgba(79,124,255,0.12);
            border:1px solid rgba(79,124,255,0.28);
            color:#bdd0ff;
            font-size:12px;
            letter-spacing:1px;
            text-transform:uppercase;
        }
        .btn {
            display:inline-block;
            padding:12px 16px;
            border-radius:14px;
            text-decoration:none;
            color:white;
            background: rgba(255,255,255,0.06);
            border:1px solid rgba(255,255,255,0.08);
        }
        .flash-error {
            margin-bottom:18px;
            padding:14px 16px;
            border-radius:14px;
            background: rgba(255,95,122,0.12);
            border: 1px solid rgba(255,95,122,0.22);
            color:#ffb7c4;
        }
        .flash-success {
            margin-bottom:18px;
            padding:14px 16px;
            border-radius:14px;
            background: rgba(40,200,120,0.12);
            border: 1px solid rgba(40,200,120,0.22);
            color:#bff5dd;
        }
        .result-grid {
            margin-top: 22px;
            display: grid;
            grid-template-columns: 1.15fr 0.85fr;
            gap: 20px;
        }
        .result-card {
            background: rgba(18,28,49,0.72);
            border:1px solid rgba(255,255,255,0.08);
            border-radius:24px;
            padding:24px;
        }
        .tiny-badge {
            display:inline-block;
            padding:8px 12px;
            border-radius:999px;
            background:rgba(79,124,255,0.12);
            border:1px solid rgba(79,124,255,0.28);
            color:#bdd0ff;
            font-size:12px;
            letter-spacing:1px;
            text-transform:uppercase;
        }
        .result-metrics {
            display:grid;
            grid-template-columns:1fr 1fr;
            gap:14px;
            margin-bottom:18px;
        }
        .metric-box {
            padding:18px;
            border-radius:18px;
            background:rgba(255,255,255,0.04);
            border:1px solid rgba(255,255,255,0.06);
        }
        .metric-label {
            color:#9eb0cc;
            margin-bottom:8px;
        }
        .metric-value {
            font-size:24px;
            font-weight:700;
        }
        .metric-value.small {
            font-size:18px;
        }
        .analysis-box {
            padding:20px;
            border-radius:18px;
            background:rgba(7,14,27,0.72);
            border:1px solid rgba(255,255,255,0.06);
            line-height:1.75;
        }
        .signal-box {
            margin-top:18px;
            white-space:pre-line;
            padding:20px;
            border-radius:18px;
            background:rgba(255,255,255,0.04);
            border:1px solid rgba(255,255,255,0.06);
            line-height:1.7;
        }
        .levels-grid {
            display:grid;
            gap:12px;
        }
        .level-item {
            padding:16px;
            border-radius:16px;
            background:rgba(255,255,255,0.04);
            border:1px solid rgba(255,255,255,0.06);
        }
        table {
            width:100%;
            border-collapse:collapse;
            margin-top:10px;
        }
        th, td {
            text-align:left;
            padding:12px;
            border-bottom:1px solid rgba(255,255,255,0.08);
            font-size:14px;
            vertical-align: middle;
        }
        th {
            color:#9eb0cc;
            font-weight:600;
        }
        .action-cell {
            white-space: nowrap;
        }
        .danger-btn {
            width:auto;
            margin-top:0;
            padding:8px 12px;
            background:linear-gradient(135deg,#ff5f7a,#d93b57);
            box-shadow:none;
        }
        .small-btn {
            padding:8px 12px;
            margin-right:8px;
        }
        @media (max-width: 1200px) {
            .form-grid, .top-fields {
                grid-template-columns: 1fr;
            }
        }
        @media (max-width: 1100px) {
            .grid, .result-grid {
                grid-template-columns: 1fr;
            }
            .top { display:block; }
        }
        @media (max-width: 700px) {
            .selection-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
    """


def _preview_script() -> str:
    return """
    <script>
        function bindPreview(inputId, imgId, placeholderId) {
            const input = document.getElementById(inputId);
            const img = document.getElementById(imgId);
            const placeholder = document.getElementById(placeholderId);

            if (!input || !img || !placeholder) return;

            input.addEventListener('change', function () {
                const file = this.files && this.files[0];
                if (!file) {
                    img.style.display = 'none';
                    img.src = '';
                    placeholder.style.display = 'block';
                    return;
                }

                const reader = new FileReader();
                reader.onload = function (e) {
                    img.src = e.target.result;
                    img.style.display = 'block';
                    placeholder.style.display = 'none';
                };
                reader.readAsDataURL(file);
            });
        }

        function bindSingleSubmit() {
            const forms = document.querySelectorAll('form');
            forms.forEach(form => {
                form.addEventListener('submit', function () {
                    const buttons = form.querySelectorAll('button[type="submit"], button:not([type])');
                    buttons.forEach(btn => {
                        btn.disabled = true;
                        if (!btn.dataset.originalText) {
                            btn.dataset.originalText = btn.innerText;
                        }
                        btn.innerText = 'Gönderiliyor...';
                    });
                }, { once: true });
            });
        }

        bindPreview('mainImageInput', 'mainPreview', 'mainPlaceholder');
        bindPreview('fractalImageInput', 'fractalPreview', 'fractalPlaceholder');
        bindPreview('adminMainImageInput', 'adminMainPreview', 'adminMainPlaceholder');
        bindPreview('adminFractalImageInput', 'adminFractalPreview', 'adminFractalPlaceholder');

        bindSingleSubmit();
    </script>
    """


def _render_analysis_result(result: dict) -> str:
    if not result:
        return ""

    display = result["display"]
    analysis_text = result["analysis_text"]
    signal_text = result["signal_text"]
    direction = result["levels"]["direction"]

    signal_color = "#ffe0b1"
    if direction == "BUY":
        signal_color = "#bff5dd"
    elif direction == "SELL":
        signal_color = "#ffc1cb"

    return f"""
    <div class="result-grid">
        <div class="result-card">
            <div class="tiny-badge">ANALİZ SONUCU</div>
            <h2>Yorum ve Sinyal</h2>

            <div class="result-metrics">
                <div class="metric-box">
                    <div class="metric-label">Yön</div>
                    <div class="metric-value" style="color:{signal_color};">{direction}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Yapı Bozulma</div>
                    <div class="metric-value small">{display['invalidation']}</div>
                </div>
            </div>

            <div class="analysis-box">{analysis_text}</div>
            <div class="signal-box">{signal_text}</div>
        </div>

        <div class="result-card">
            <div class="tiny-badge">SEVİYELER</div>
            <h2>Destek / Direnç</h2>
            <div class="levels-grid">
                <div class="level-item">Fraktal Destek 1: <strong>{display['fractal_support_1']}</strong></div>
                <div class="level-item">Fraktal Destek 2: <strong>{display['fractal_support_2']}</strong></div>
                <div class="level-item">Fraktal Direnç 1: <strong>{display['fractal_resistance_1']}</strong></div>
                <div class="level-item">Fraktal Direnç 2: <strong>{display['fractal_resistance_2']}</strong></div>
                <div class="level-item">Ana Destek: <strong>{display['main_support']}</strong></div>
                <div class="level-item">Ana Direnç: <strong>{display['main_resistance']}</strong></div>
            </div>
        </div>
    </div>
    """


def render_user_dashboard(
    user: User,
    error: str = "",
    success: str = "",
    result: dict | None = None,
) -> HTMLResponse:
    error_html = f'<div class="flash-error">{error}</div>' if error else ""
    success_html = f'<div class="flash-success">{success}</div>' if success else ""
    result_html = _render_analysis_result(result)

    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Kullanıcı Paneli</title>
        {_shared_styles()}
    </head>
    <body>
        <div class="wrap">
            <div class="top">
                <div>
                    <div class="tiny">KULLANICI PANELİ</div>
                    <h1 style="margin:10px 0 6px;">Hoş geldin {user.display_name or user.username}</h1>
                    <div style="color:#9eb0cc;">Şirket: {user.company_name or "-"}</div>
                </div>
                <div style="margin-top:12px;">
                    <a class="btn" href="/logout">Çıkış</a>
                </div>
            </div>

            {error_html}
            {success_html}

            <div class="grid">
                <div class="card">
                    <div class="tiny">PLAN</div>
                    <h3>{user.subscription_plan or "-"}</h3>
                    <p>Gönderim yetkileri kullanıcı bazlı çalışır.</p>
                </div>
                <div class="card">
                    <div class="tiny">TELEGRAM</div>
                    <h3>{'Hazır' if user.telegram_bot_token and user.telegram_chat_id else 'Eksik'}</h3>
                    <p>Kendi bot ve chat id bilgilerin kullanılır.</p>
                </div>
                <div class="card">
                    <div class="tiny">BRANDING</div>
                    <h3>{'Hazır' if user.frame_main_path and user.frame_fractal_path else 'Eksik'}</h3>
                    <p>Kendi frame ve logo dosyaların kullanılır.</p>
                </div>
            </div>

            <div class="form-card">
                <div class="tiny-badge">ANALİZ ÜRET</div>
                <h2>Kendi Telegram Alanına Gönder</h2>

                <form method="post" action="/user/analyze" enctype="multipart/form-data">
                    <div class="top-fields">
                        <div class="field">
                            <label>Enstrüman</label>
                            <input type="text" name="instrument" placeholder="Örn: Gold, DAX, NASDAQ, EUR/USD" required>
                        </div>

                        <div class="field">
                            <label>Anlık Fiyat</label>
                            <input type="number" step="any" name="current_price" placeholder="Örn: 4424,00" required>
                        </div>
                    </div>

                    <div class="form-grid">
                        <div class="image-card">
                            <h3>Ana Dalga Görseli</h3>

                            <div class="preview-box">
                                <img id="mainPreview" alt="Ana dalga önizleme">
                                <div class="preview-placeholder" id="mainPlaceholder">
                                    Henüz ana dalga görseli seçilmedi
                                </div>
                            </div>

                            <div class="field">
                                <label>Görsel Yükle</label>
                                <input type="file" id="mainImageInput" name="main_image" accept="image/*" required>
                            </div>

                            <div class="selection-grid">
                                <div class="field">
                                    <label>Ana Pattern</label>
                                    <select name="main_pattern">
                                        <option>Impuls</option>
                                        <option>Diagonal</option>
                                        <option selected>ABC</option>
                                        <option>WXY</option>
                                    </select>
                                </div>

                                <div class="field">
                                    <label>Ana Subwave</label>
                                    <select name="main_subwave">
                                        <option>Wave 1</option>
                                        <option>Wave 2</option>
                                        <option>Wave 3</option>
                                        <option>Wave 4</option>
                                        <option>Wave 5</option>
                                        <option>Wave A</option>
                                        <option>Wave B</option>
                                        <option selected>Wave C</option>
                                        <option>Wave W</option>
                                        <option>Wave X</option>
                                        <option>Wave Y</option>
                                    </select>
                                </div>
                            </div>

                            <label class="checkline">
                                <input type="checkbox" name="main_reverse_mode">
                                Ana Reverse Açık
                            </label>
                        </div>

                        <div class="image-card">
                            <h3>Fraktal Dalga Görseli</h3>

                            <div class="preview-box">
                                <img id="fractalPreview" alt="Fraktal dalga önizleme">
                                <div class="preview-placeholder" id="fractalPlaceholder">
                                    Henüz fraktal dalga görseli seçilmedi
                                </div>
                            </div>

                            <div class="field">
                                <label>Görsel Yükle</label>
                                <input type="file" id="fractalImageInput" name="fractal_image" accept="image/*" required>
                            </div>

                            <div class="selection-grid">
                                <div class="field">
                                    <label>Fraktal Pattern</label>
                                    <select name="fractal_pattern">
                                        <option selected>Impuls</option>
                                        <option>Diagonal</option>
                                        <option>ABC</option>
                                        <option>WXY</option>
                                    </select>
                                </div>

                                <div class="field">
                                    <label>Fraktal Subwave</label>
                                    <select name="fractal_subwave">
                                        <option>Wave 1</option>
                                        <option>Wave 2</option>
                                        <option>Wave 3</option>
                                        <option selected>Wave 4</option>
                                        <option>Wave 5</option>
                                        <option>Wave A</option>
                                        <option>Wave B</option>
                                        <option>Wave C</option>
                                        <option>Wave W</option>
                                        <option>Wave X</option>
                                        <option>Wave Y</option>
                                    </select>
                                </div>
                            </div>

                            <label class="checkline">
                                <input type="checkbox" name="fractal_reverse_mode">
                                Fraktal Reverse Açık
                            </label>
                        </div>
                    </div>

                    <label class="checkline" style="margin-top:18px;">
                        <input type="checkbox" name="send_telegram" checked>
                        Analiz sonrası kendi Telegram alanıma gönder
                    </label>

                    <button type="submit">Analiz ve Yorumu Gönder</button>
                </form>
            </div>

            <div class="form-card">
                <div class="tiny-badge">TEK İÇERİK KARTI</div>
                <h2>Haber / Veri Kartı Gönder</h2>

                <form method="post" action="/user/send-card" enctype="multipart/form-data">
                    <div class="top-fields">
                        <div class="field">
                            <label>Kart Türü</label>
                            <select name="card_type" required>
                                <option value="news">Haber</option>
                                <option value="data">Veri</option>
                            </select>
                        </div>

                        <div class="field">
                            <label>Görsel</label>
                            <input type="file" name="content_image" accept="image/*">
                        </div>
                    </div>

                    <div class="field">
                        <label>Başlık</label>
                        <input type="text" name="title" placeholder="Başlık yaz..." required>
                    </div>

                    <div class="field">
                        <label>İçerik</label>
                        <textarea name="body" placeholder="İçerik yaz..." required></textarea>
                    </div>

                    <button type="submit">Kartı Telegram’a Gönder</button>
                </form>
            </div>

            {result_html}
        </div>
        {_preview_script()}
    </body>
    </html>
    """)


def render_admin_dashboard(
    admin: User,
    users: list[User],
    error: str = "",
    success: str = "",
    result: dict | None = None,
) -> HTMLResponse:
    error_html = f'<div class="flash-error">{error}</div>' if error else ""
    success_html = f'<div class="flash-success">{success}</div>' if success else ""
    result_html = _render_analysis_result(result)

    user_options = ""
    rows_html = ""

    for u in users:
        if u.username != "admin":
            user_options += f'<option value="{u.id}">{u.display_name or u.username} | {u.company_name or "-"}</option>'

        if u.username == "admin":
            continue

        rows_html += f"""
        <tr>
            <td>{u.id}</td>
            <td><a href="/admin/users/{u.id}/edit" style="color:#bdd0ff;text-decoration:none;">{u.username}</a></td>
            <td>{u.display_name or "-"}</td>
            <td>{u.company_name or "-"}</td>
            <td>{u.subscription_plan or "-"}</td>
            <td>{"Aktif" if u.is_active else "Pasif"}</td>
            <td>{u.telegram_chat_id or "-"}</td>
            <td class="action-cell">
                <a class="btn small-btn" href="/admin/users/{u.id}/edit">Güncelle</a>
                <form method="post" action="/admin/users/{u.id}/delete" style="display:inline;" onsubmit="return confirm('Bu kullanıcı silinsin mi?');">
                    <button type="submit" class="danger-btn">Sil</button>
                </form>
            </td>
        </tr>
        """

    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Admin Panel</title>
        {_shared_styles()}
    </head>
    <body>
        <div class="wrap">
            <div class="top">
                <div>
                    <div class="tiny">ADMIN PANEL</div>
                    <h1 style="margin:10px 0 6px;">Kullanıcı Yönetimi ve Dağıtım</h1>
                    <div style="color:#9eb0cc;">Hoş geldin {admin.display_name or admin.username}</div>
                </div>
                <div style="margin-top:12px;">
                    <a class="btn" href="/logout">Çıkış</a>
                </div>
            </div>

            {error_html}
            {success_html}

            <div class="grid">
                <div class="card">
                    <div class="tiny">KULLANICI</div>
                    <h3>{len([u for u in users if u.username != 'admin'])}</h3>
                    <p>Kayıtlı müşteri hesabı</p>
                </div>
                <div class="card">
                    <div class="tiny">CONTENT</div>
                    <h3>Analiz + İçerik Kartı</h3>
                    <p>Admin seçili kullanıcı adına branded yayın yapabilir</p>
                </div>
                <div class="card">
                    <div class="tiny">FRAME</div>
                    <h3>Kullanıcı Bazlı</h3>
                    <p>Her kullanıcı kendi logo ve frame setiyle yayın alır</p>
                </div>
            </div>

            <div class="form-card">
                <div class="tiny-badge">ADMİN ANALİZ GÖNDERİMİ</div>
                <h2>Seçili Kullanıcı Adına Analiz Gönder</h2>

                <form method="post" action="/admin/analyze-for-user" enctype="multipart/form-data">
                    <div class="field">
                        <label>Hedef Kullanıcı</label>
                        <select name="target_user_id" required>
                            <option value="">Kullanıcı seç</option>
                            {user_options}
                        </select>
                    </div>

                    <div class="top-fields">
                        <div class="field">
                            <label>Enstrüman</label>
                            <input type="text" name="instrument" placeholder="Örn: Gold, DAX, NASDAQ, EUR/USD" required>
                        </div>

                        <div class="field">
                            <label>Anlık Fiyat</label>
                            <input type="number" step="any" name="current_price" placeholder="Örn: 4424,00" required>
                        </div>
                    </div>

                    <div class="form-grid">
                        <div class="image-card">
                            <h3>Ana Dalga Görseli</h3>

                            <div class="preview-box">
                                <img id="adminMainPreview" alt="Ana dalga önizleme">
                                <div class="preview-placeholder" id="adminMainPlaceholder">
                                    Henüz ana dalga görseli seçilmedi
                                </div>
                            </div>

                            <div class="field">
                                <label>Görsel Yükle</label>
                                <input type="file" id="adminMainImageInput" name="main_image" accept="image/*" required>
                            </div>

                            <div class="selection-grid">
                                <div class="field">
                                    <label>Ana Pattern</label>
                                    <select name="main_pattern">
                                        <option>Impuls</option>
                                        <option>Diagonal</option>
                                        <option selected>ABC</option>
                                        <option>WXY</option>
                                    </select>
                                </div>

                                <div class="field">
                                    <label>Ana Subwave</label>
                                    <select name="main_subwave">
                                        <option>Wave 1</option>
                                        <option>Wave 2</option>
                                        <option>Wave 3</option>
                                        <option>Wave 4</option>
                                        <option>Wave 5</option>
                                        <option>Wave A</option>
                                        <option>Wave B</option>
                                        <option selected>Wave C</option>
                                        <option>Wave W</option>
                                        <option>Wave X</option>
                                        <option>Wave Y</option>
                                    </select>
                                </div>
                            </div>

                            <label class="checkline">
                                <input type="checkbox" name="main_reverse_mode">
                                Ana Reverse Açık
                            </label>
                        </div>

                        <div class="image-card">
                            <h3>Fraktal Dalga Görseli</h3>

                            <div class="preview-box">
                                <img id="adminFractalPreview" alt="Fraktal dalga önizleme">
                                <div class="preview-placeholder" id="adminFractalPlaceholder">
                                    Henüz fraktal dalga görseli seçilmedi
                                </div>
                            </div>

                            <div class="field">
                                <label>Görsel Yükle</label>
                                <input type="file" id="adminFractalImageInput" name="fractal_image" accept="image/*" required>
                            </div>

                            <div class="selection-grid">
                                <div class="field">
                                    <label>Fraktal Pattern</label>
                                    <select name="fractal_pattern">
                                        <option selected>Impuls</option>
                                        <option>Diagonal</option>
                                        <option>ABC</option>
                                        <option>WXY</option>
                                    </select>
                                </div>

                                <div class="field">
                                    <label>Fraktal Subwave</label>
                                    <select name="fractal_subwave">
                                        <option>Wave 1</option>
                                        <option>Wave 2</option>
                                        <option>Wave 3</option>
                                        <option selected>Wave 4</option>
                                        <option>Wave 5</option>
                                        <option>Wave A</option>
                                        <option>Wave B</option>
                                        <option>Wave C</option>
                                        <option>Wave W</option>
                                        <option>Wave X</option>
                                        <option>Wave Y</option>
                                    </select>
                                </div>
                            </div>

                            <label class="checkline">
                                <input type="checkbox" name="fractal_reverse_mode">
                                Fraktal Reverse Açık
                            </label>
                        </div>
                    </div>

                    <label class="checkline" style="margin-top:18px;">
                        <input type="checkbox" name="send_telegram" checked>
                        Seçili kullanıcının Telegram alanına gönder
                    </label>

                    <button type="submit">Kullanıcı Adına Analiz Gönder</button>
                </form>
            </div>

            <div class="form-card">
                <div class="tiny-badge">TEK İÇERİK KARTI</div>
                <h2>Seçili Kullanıcı Adına Haber / Veri Kartı Gönder</h2>

                <form method="post" action="/admin/send-card-for-user" enctype="multipart/form-data">
                    <div class="field">
                        <label>Hedef Kullanıcı</label>
                        <select name="target_user_id" required>
                            <option value="">Kullanıcı seç</option>
                            {user_options}
                        </select>
                    </div>

                    <div class="top-fields">
                        <div class="field">
                            <label>Kart Türü</label>
                            <select name="card_type" required>
                                <option value="news">Haber</option>
                                <option value="data">Veri</option>
                            </select>
                        </div>

                        <div class="field">
                            <label>Görsel</label>
                            <input type="file" name="content_image" accept="image/*">
                        </div>
                    </div>

                    <div class="field">
                        <label>Başlık</label>
                        <input type="text" name="title" placeholder="Başlık yaz..." required>
                    </div>

                    <div class="field">
                        <label>İçerik</label>
                        <textarea name="body" placeholder="İçerik yaz..." required></textarea>
                    </div>

                    <button type="submit">Kartı Gönder</button>
                </form>
            </div>

            <div class="form-card">
                <div class="tiny-badge">YENİ KULLANICI</div>
                <h2>Yeni Kullanıcı Ekle</h2>

                <form method="post" action="/admin/users/create" enctype="multipart/form-data">
                    <div class="form-grid">
                        <div>
                            <div class="field">
                                <label>Kullanıcı Adı</label>
                                <input type="text" name="username" required>
                            </div>
                            <div class="field">
                                <label>Şifre</label>
                                <input type="text" name="password" required>
                            </div>
                            <div class="field">
                                <label>Görünen Ad</label>
                                <input type="text" name="display_name">
                            </div>
                            <div class="field">
                                <label>Şirket Adı</label>
                                <input type="text" name="company_name">
                            </div>
                            <div class="field">
                                <label>Plan</label>
                                <select name="subscription_plan">
                                    <option value="standard">standard</option>
                                    <option value="pro">pro</option>
                                    <option value="premium">premium</option>
                                </select>
                            </div>
                            <div class="field">
                                <label>Üyelik Bitiş Tarihi</label>
                                <input type="date" name="subscription_end_date">
                            </div>
                        </div>

                        <div>
                            <div class="field">
                                <label>Telegram Bot Token</label>
                                <input type="text" name="telegram_bot_token">
                            </div>
                            <div class="field">
                                <label>Telegram Chat ID</label>
                                <input type="text" name="telegram_chat_id">
                            </div>
                            <div class="field">
                                <label>Logo</label>
                                <input type="file" name="logo_file" accept="image/*">
                            </div>
                            <div class="field">
                                <label>Main Frame</label>
                                <input type="file" name="frame_main_file" accept="image/*">
                            </div>
                            <div class="field">
                                <label>Fractal Frame</label>
                                <input type="file" name="frame_fractal_file" accept="image/*">
                            </div>
                            <div class="field">
                                <label>News Frame</label>
                                <input type="file" name="frame_news_file" accept="image/*">
                            </div>
                            <div class="field">
                                <label>Data Frame</label>
                                <input type="file" name="frame_data_file" accept="image/*">
                            </div>
                        </div>
                    </div>

                    <label class="checkline"><input type="checkbox" name="is_active" checked> Aktif Kullanıcı</label>
                    <label class="checkline"><input type="checkbox" name="can_send_analysis" checked> Analiz Gönderimi</label>
                    <label class="checkline"><input type="checkbox" name="can_send_signal" checked> Sinyal Gönderimi</label>
                    <label class="checkline"><input type="checkbox" name="can_send_news"> Haber Gönderimi</label>
                    <label class="checkline"><input type="checkbox" name="can_send_data_calendar"> Veri Takvimi Gönderimi</label>

                    <button type="submit">Kullanıcıyı Kaydet</button>
                </form>
            </div>

            <div class="form-card">
                <div class="tiny-badge">KULLANICI LİSTESİ</div>
                <h2>Kayıtlı Kullanıcılar</h2>
                <div style="overflow:auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Kullanıcı</th>
                                <th>Görünen Ad</th>
                                <th>Şirket</th>
                                <th>Plan</th>
                                <th>Durum</th>
                                <th>Chat ID</th>
                                <th>İşlemler</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows_html}
                        </tbody>
                    </table>
                </div>
            </div>

            {result_html}
        </div>
        {_preview_script()}
    </body>
    </html>
    """)


def render_edit_user_page(
    admin: User,
    target_user: User,
    error: str = "",
    success: str = "",
) -> HTMLResponse:
    error_html = f'<div class="flash-error">{error}</div>' if error else ""
    success_html = f'<div class="flash-success">{success}</div>' if success else ""

    subscription_end_value = ""
    if target_user.subscription_end_date:
        subscription_end_value = target_user.subscription_end_date.strftime("%Y-%m-%d")

    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Kullanıcı Güncelle</title>
        {_shared_styles()}
    </head>
    <body>
        <div class="wrap">
            <div class="top">
                <div>
                    <div class="tiny">KULLANICI GÜNCELLE</div>
                    <h1 style="margin:10px 0 6px;">{target_user.display_name or target_user.username}</h1>
                    <div style="color:#9eb0cc;">ID: {target_user.id} | Kullanıcı adı: {target_user.username}</div>
                </div>
                <div style="margin-top:12px;">
                    <a class="btn" href="/dashboard">Panele Dön</a>
                </div>
            </div>

            {error_html}
            {success_html}

            <div class="form-card">
                <div class="tiny-badge">KULLANICI DÜZENLE</div>
                <h2>Bilgileri Güncelle</h2>

                <form method="post" action="/admin/users/{target_user.id}/update" enctype="multipart/form-data">
                    <div class="form-grid">
                        <div>
                            <div class="field">
                                <label>Kullanıcı Adı</label>
                                <input type="text" name="username" value="{target_user.username}" required>
                            </div>
                            <div class="field">
                                <label>Yeni Şifre</label>
                                <input type="text" name="password" placeholder="Boş bırakırsan değişmez">
                            </div>
                            <div class="field">
                                <label>Görünen Ad</label>
                                <input type="text" name="display_name" value="{target_user.display_name or ''}">
                            </div>
                            <div class="field">
                                <label>Şirket Adı</label>
                                <input type="text" name="company_name" value="{target_user.company_name or ''}">
                            </div>
                            <div class="field">
                                <label>Plan</label>
                                <select name="subscription_plan">
                                    <option value="standard" {"selected" if target_user.subscription_plan == "standard" else ""}>standard</option>
                                    <option value="pro" {"selected" if target_user.subscription_plan == "pro" else ""}>pro</option>
                                    <option value="premium" {"selected" if target_user.subscription_plan == "premium" else ""}>premium</option>
                                    <option value="lifetime" {"selected" if target_user.subscription_plan == "lifetime" else ""}>lifetime</option>
                                </select>
                            </div>
                            <div class="field">
                                <label>Üyelik Bitiş Tarihi</label>
                                <input type="date" name="subscription_end_date" value="{subscription_end_value}">
                            </div>
                        </div>

                        <div>
                            <div class="field">
                                <label>Telegram Bot Token</label>
                                <input type="text" name="telegram_bot_token" value="{target_user.telegram_bot_token or ''}">
                            </div>
                            <div class="field">
                                <label>Telegram Chat ID</label>
                                <input type="text" name="telegram_chat_id" value="{target_user.telegram_chat_id or ''}">
                            </div>
                            <div class="field">
                                <label>Yeni Logo</label>
                                <input type="file" name="logo_file" accept="image/*">
                            </div>
                            <div class="field">
                                <label>Yeni Main Frame</label>
                                <input type="file" name="frame_main_file" accept="image/*">
                            </div>
                            <div class="field">
                                <label>Yeni Fractal Frame</label>
                                <input type="file" name="frame_fractal_file" accept="image/*">
                            </div>
                            <div class="field">
                                <label>Yeni News Frame</label>
                                <input type="file" name="frame_news_file" accept="image/*">
                            </div>
                            <div class="field">
                                <label>Yeni Data Frame</label>
                                <input type="file" name="frame_data_file" accept="image/*">
                            </div>
                        </div>
                    </div>

                    <label class="checkline"><input type="checkbox" name="is_active" {"checked" if target_user.is_active else ""}> Aktif Kullanıcı</label>
                    <label class="checkline"><input type="checkbox" name="can_send_analysis" {"checked" if target_user.can_send_analysis else ""}> Analiz Gönderimi</label>
                    <label class="checkline"><input type="checkbox" name="can_send_signal" {"checked" if target_user.can_send_signal else ""}> Sinyal Gönderimi</label>
                    <label class="checkline"><input type="checkbox" name="can_send_news" {"checked" if target_user.can_send_news else ""}> Haber Gönderimi</label>
                    <label class="checkline"><input type="checkbox" name="can_send_data_calendar" {"checked" if target_user.can_send_data_calendar else ""}> Veri Takvimi Gönderimi</label>

                    <button type="submit">Kullanıcıyı Güncelle</button>
                </form>
            </div>
        </div>
    </body>
    </html>
    """)


@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return render_login_page()


@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username.strip()).first()

    if not user or not verify_password(password, user.password_hash):
        return render_login_page("Kullanıcı adı veya şifre hatalı.")

    if not user.is_active:
        return render_login_page("Bu kullanıcı pasif durumda.")

    request.session["user_id"] = user.id
    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    users = db.query(User).order_by(User.id.desc()).all()

    if user.role == "super_admin":
        return render_admin_dashboard(admin=user, users=users)

    return render_user_dashboard(user=user)


@app.get("/admin/users/{user_id}/edit", response_class=HTMLResponse)
def edit_user_page(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    admin = get_current_user(request, db)
    if not admin:
        return RedirectResponse(url="/login", status_code=302)

    try:
        require_admin(admin)
        target_user = get_user_or_none(db, user_id)

        if not target_user or target_user.username == "admin":
            users = db.query(User).order_by(User.id.desc()).all()
            return render_admin_dashboard(admin, users, error="Kullanıcı bulunamadı.")

        return render_edit_user_page(admin, target_user)

    except PermissionError as e:
        return HTMLResponse(str(e), status_code=403)


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
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    users = db.query(User).order_by(User.id.desc()).all()

    try:
        require_admin(current_user)

        exists = db.query(User).filter(User.username == username.strip()).first()
        if exists:
            return render_admin_dashboard(current_user, users, error="Bu kullanıcı adı zaten kayıtlı.")

        logo_path = save_uploaded_file(logo_file, "logo")
        frame_main_path = save_uploaded_file(frame_main_file, "frame_main")
        frame_fractal_path = save_uploaded_file(frame_fractal_file, "frame_fractal")
        frame_news_path = save_uploaded_file(frame_news_file, "frame_news")
        frame_data_path = save_uploaded_file(frame_data_file, "frame_data")

        user = User(
            username=username.strip(),
            password_hash=hash_password(password.strip()),
            role="user",
            company_name=company_name.strip(),
            display_name=display_name.strip(),
            logo_path=logo_path,
            frame_main_path=frame_main_path,
            frame_fractal_path=frame_fractal_path,
            frame_news_path=frame_news_path,
            frame_data_path=frame_data_path,
            telegram_bot_token=telegram_bot_token.strip(),
            telegram_chat_id=telegram_chat_id.strip(),
            is_active=parse_bool_checkbox(is_active),
            can_send_analysis=parse_bool_checkbox(can_send_analysis),
            can_send_signal=parse_bool_checkbox(can_send_signal),
            can_send_news=parse_bool_checkbox(can_send_news),
            can_send_data_calendar=parse_bool_checkbox(can_send_data_calendar),
            subscription_plan=subscription_plan.strip() or "standard",
            subscription_end_date=parse_date(subscription_end_date),
        )

        db.add(user)
        db.commit()

        users = db.query(User).order_by(User.id.desc()).all()
        return render_admin_dashboard(current_user, users, success="Kullanıcı başarıyla oluşturuldu.")

    except PermissionError as e:
        return HTMLResponse(str(e), status_code=403)
    except Exception as e:
        return render_admin_dashboard(current_user, users, error=f"Hata: {e}")


@app.post("/admin/users/{user_id}/update", response_class=HTMLResponse)
def update_user(
    user_id: int,
    request: Request,
    username: str = Form(...),
    password: str = Form(""),
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
    db: Session = Depends(get_db),
):
    admin = get_current_user(request, db)
    if not admin:
        return RedirectResponse(url="/login", status_code=302)

    try:
        require_admin(admin)

        target_user = get_user_or_none(db, user_id)
        if not target_user or target_user.username == "admin":
            users = db.query(User).order_by(User.id.desc()).all()
            return render_admin_dashboard(admin, users, error="Kullanıcı bulunamadı.")

        existing = db.query(User).filter(User.username == username.strip(), User.id != user_id).first()
        if existing:
            return render_edit_user_page(admin, target_user, error="Bu kullanıcı adı başka bir hesapta kayıtlı.")

        target_user.username = username.strip()
        target_user.display_name = display_name.strip()
        target_user.company_name = company_name.strip()
        target_user.subscription_plan = subscription_plan.strip() or "standard"
        target_user.subscription_end_date = parse_date(subscription_end_date)
        target_user.telegram_bot_token = telegram_bot_token.strip()
        target_user.telegram_chat_id = telegram_chat_id.strip()

        target_user.is_active = parse_bool_checkbox(is_active)
        target_user.can_send_analysis = parse_bool_checkbox(can_send_analysis)
        target_user.can_send_signal = parse_bool_checkbox(can_send_signal)
        target_user.can_send_news = parse_bool_checkbox(can_send_news)
        target_user.can_send_data_calendar = parse_bool_checkbox(can_send_data_calendar)

        if password.strip():
            target_user.password_hash = hash_password(password.strip())

        target_user.logo_path = replace_uploaded_file(logo_file, target_user.logo_path, "logo")
        target_user.frame_main_path = replace_uploaded_file(frame_main_file, target_user.frame_main_path, "frame_main")
        target_user.frame_fractal_path = replace_uploaded_file(frame_fractal_file, target_user.frame_fractal_path, "frame_fractal")
        target_user.frame_news_path = replace_uploaded_file(frame_news_file, target_user.frame_news_path, "frame_news")
        target_user.frame_data_path = replace_uploaded_file(frame_data_file, target_user.frame_data_path, "frame_data")

        db.commit()
        db.refresh(target_user)

        return render_edit_user_page(admin, target_user, success="Kullanıcı başarıyla güncellendi.")

    except PermissionError as e:
        return HTMLResponse(str(e), status_code=403)
    except Exception as e:
        target_user = get_user_or_none(db, user_id)
        if target_user:
            return render_edit_user_page(admin, target_user, error=f"Hata: {e}")
        users = db.query(User).order_by(User.id.desc()).all()
        return render_admin_dashboard(admin, users, error=f"Hata: {e}")


@app.post("/admin/users/{user_id}/delete", response_class=HTMLResponse)
def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    admin = get_current_user(request, db)
    if not admin:
        return RedirectResponse(url="/login", status_code=302)

    users = db.query(User).order_by(User.id.desc()).all()

    try:
        require_admin(admin)

        target_user = get_user_or_none(db, user_id)
        if not target_user or target_user.username == "admin":
            return render_admin_dashboard(admin, users, error="Kullanıcı bulunamadı veya silinemez.")

        delete_file_if_exists(target_user.logo_path)
        delete_file_if_exists(target_user.frame_main_path)
        delete_file_if_exists(target_user.frame_fractal_path)
        delete_file_if_exists(target_user.frame_news_path)
        delete_file_if_exists(target_user.frame_data_path)

        db.delete(target_user)
        db.commit()

        users = db.query(User).order_by(User.id.desc()).all()
        return render_admin_dashboard(admin, users, success="Kullanıcı silindi.")

    except PermissionError as e:
        return HTMLResponse(str(e), status_code=403)
    except Exception as e:
        return render_admin_dashboard(admin, users, error=f"Hata: {e}")


@app.post("/user/analyze", response_class=HTMLResponse)
def user_analyze(
    request: Request,
    instrument: str = Form(...),
    current_price: float = Form(...),
    main_pattern: str = Form(...),
    main_subwave: str = Form(...),
    fractal_pattern: str = Form(...),
    fractal_subwave: str = Form(...),
    main_reverse_mode: str | None = Form(None),
    fractal_reverse_mode: str | None = Form(None),
    send_telegram: str | None = Form(None),
    main_image: UploadFile = File(...),
    fractal_image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    if user.role == "super_admin":
        users = db.query(User).order_by(User.id.desc()).all()
        return render_admin_dashboard(user, users, error="Bu ekran kullanıcılar içindir.")

    if not user.can_send_analysis:
        return render_user_dashboard(user, error="Bu kullanıcı için analiz yetkisi kapalı.")

    try:
        main_image_path = save_uploaded_file(main_image, "user_main")
        fractal_image_path = save_uploaded_file(fractal_image, "user_fractal")

        result = run_full_analysis(
            main_image_path=main_image_path,
            fractal_image_path=fractal_image_path,
            instrument=instrument,
            current_price=current_price,
            main_pattern=main_pattern,
            main_subwave=main_subwave,
            fractal_pattern=fractal_pattern,
            fractal_subwave=fractal_subwave,
            main_reverse_mode=parse_bool_checkbox(main_reverse_mode),
            fractal_reverse_mode=parse_bool_checkbox(fractal_reverse_mode),
            api_key=None,
        )

        success_message = "Analiz üretildi."

        if send_telegram:
            if not user.telegram_bot_token or not user.telegram_chat_id:
                success_message = "Analiz üretildi ancak Telegram bot token veya chat id eksik."
            elif not user.frame_main_path or not user.frame_fractal_path:
                success_message = "Analiz üretildi ancak kullanıcı frame dosyaları eksik."
            else:
                send_analysis_bundle(
                    instrument_name=instrument.upper(),
                    display_levels=result["display"],
                    analysis_text=result["analysis_text"],
                    signal_text=result["signal_text"],
                    main_image_path=main_image_path,
                    fractal_image_path=fractal_image_path,
                    main_frame_path=user.frame_main_path,
                    fractal_frame_path=user.frame_fractal_path,
                    token=user.telegram_bot_token,
                    chat_id=user.telegram_chat_id,
                )
                success_message = "Analiz ve sinyal, kendi Telegram alanına kendi frame’lerin ile gönderildi."

        return render_user_dashboard(user=user, result=result, success=success_message)

    except Exception as e:
        return render_user_dashboard(user=user, error=f"Hata: {e}")


@app.post("/user/send-card", response_class=HTMLResponse)
def user_send_card(
    request: Request,
    card_type: str = Form(...),
    title: str = Form(...),
    body: str = Form(...),
    content_image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    if card_type not in {"news", "data"}:
        return render_user_dashboard(user, error="Geçersiz kart tipi.")

    if card_type == "news" and not user.can_send_news:
        return render_user_dashboard(user, error="Bu kullanıcı için haber gönderim yetkisi kapalı.")

    if card_type == "data" and not user.can_send_data_calendar:
        return render_user_dashboard(user, error="Bu kullanıcı için veri takvimi gönderim yetkisi kapalı.")

    try:
        if not user.telegram_bot_token or not user.telegram_chat_id:
            return render_user_dashboard(user, error="Telegram bot token veya chat id eksik.")

        frame_path = get_content_frame_path(user, card_type)
        if not frame_path:
            return render_user_dashboard(user, error=f"{card_type_label(card_type)} frame dosyası eksik.")

        content_image_path = save_uploaded_file(content_image, f"{card_type}_content") if content_image and content_image.filename else ""

        if card_type == "news":
            send_news_bundle(
                title=title,
                body=body,
                frame_path=frame_path,
                logo_path=user.logo_path or "",
                footer_text=footer_for_user(user),
                content_image_path=content_image_path,
                token=user.telegram_bot_token,
                chat_id=user.telegram_chat_id,
            )
        else:
            send_data_bundle(
                title=title,
                body=body,
                frame_path=frame_path,
                logo_path=user.logo_path or "",
                footer_text=footer_for_user(user),
                content_image_path=content_image_path,
                token=user.telegram_bot_token,
                chat_id=user.telegram_chat_id,
            )

        return render_user_dashboard(user, success=f"{card_type_label(card_type)} kartı kendi Telegram alanına gönderildi.")
    except Exception as e:
        return render_user_dashboard(user, error=f"Hata: {e}")


@app.post("/admin/analyze-for-user", response_class=HTMLResponse)
def admin_analyze_for_user(
    request: Request,
    target_user_id: int = Form(...),
    instrument: str = Form(...),
    current_price: float = Form(...),
    main_pattern: str = Form(...),
    main_subwave: str = Form(...),
    fractal_pattern: str = Form(...),
    fractal_subwave: str = Form(...),
    main_reverse_mode: str | None = Form(None),
    fractal_reverse_mode: str | None = Form(None),
    send_telegram: str | None = Form(None),
    main_image: UploadFile = File(...),
    fractal_image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    admin = get_current_user(request, db)
    if not admin:
        return RedirectResponse(url="/login", status_code=302)

    users = db.query(User).order_by(User.id.desc()).all()

    try:
        require_admin(admin)

        target_user = db.query(User).filter(User.id == target_user_id).first()
        if not target_user or target_user.username == "admin":
            return render_admin_dashboard(admin, users, error="Geçerli bir kullanıcı seçilmedi.")

        if not target_user.is_active:
            return render_admin_dashboard(admin, users, error="Seçilen kullanıcı pasif durumda.")

        if not target_user.can_send_analysis:
            return render_admin_dashboard(admin, users, error="Seçilen kullanıcı için analiz yetkisi kapalı.")

        main_image_path = save_uploaded_file(main_image, "admin_main")
        fractal_image_path = save_uploaded_file(fractal_image, "admin_fractal")

        result = run_full_analysis(
            main_image_path=main_image_path,
            fractal_image_path=fractal_image_path,
            instrument=instrument,
            current_price=current_price,
            main_pattern=main_pattern,
            main_subwave=main_subwave,
            fractal_pattern=fractal_pattern,
            fractal_subwave=fractal_subwave,
            main_reverse_mode=parse_bool_checkbox(main_reverse_mode),
            fractal_reverse_mode=parse_bool_checkbox(fractal_reverse_mode),
            api_key=None,
        )

        success_message = f"{target_user.display_name or target_user.username} adına analiz üretildi."

        if send_telegram:
            if not target_user.telegram_bot_token or not target_user.telegram_chat_id:
                success_message = "Analiz üretildi ancak hedef kullanıcının Telegram bot token veya chat id bilgisi eksik."
            elif not target_user.frame_main_path or not target_user.frame_fractal_path:
                success_message = "Analiz üretildi ancak hedef kullanıcının frame dosyaları eksik."
            else:
                send_analysis_bundle(
                    instrument_name=instrument.upper(),
                    display_levels=result["display"],
                    analysis_text=result["analysis_text"],
                    signal_text=result["signal_text"],
                    main_image_path=main_image_path,
                    fractal_image_path=fractal_image_path,
                    main_frame_path=target_user.frame_main_path,
                    fractal_frame_path=target_user.frame_fractal_path,
                    token=target_user.telegram_bot_token,
                    chat_id=target_user.telegram_chat_id,
                )
                success_message = f"{target_user.display_name or target_user.username} adına Telegram gönderimi tamamlandı."

        return render_admin_dashboard(admin, users, success=success_message, result=result)

    except PermissionError as e:
        return HTMLResponse(str(e), status_code=403)
    except Exception as e:
        return render_admin_dashboard(admin, users, error=f"Hata: {e}")


@app.post("/admin/send-card-for-user", response_class=HTMLResponse)
def admin_send_card_for_user(
    request: Request,
    target_user_id: int = Form(...),
    card_type: str = Form(...),
    title: str = Form(...),
    body: str = Form(...),
    content_image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    admin = get_current_user(request, db)
    if not admin:
        return RedirectResponse(url="/login", status_code=302)

    users = db.query(User).order_by(User.id.desc()).all()

    try:
        require_admin(admin)

        if card_type not in {"news", "data"}:
            return render_admin_dashboard(admin, users, error="Geçersiz kart tipi.")

        target_user = db.query(User).filter(User.id == target_user_id).first()
        if not target_user or target_user.username == "admin":
            return render_admin_dashboard(admin, users, error="Geçerli bir kullanıcı seçilmedi.")

        if not target_user.is_active:
            return render_admin_dashboard(admin, users, error="Seçilen kullanıcı pasif durumda.")

        if card_type == "news" and not target_user.can_send_news:
            return render_admin_dashboard(admin, users, error="Seçilen kullanıcı için haber gönderim yetkisi kapalı.")

        if card_type == "data" and not target_user.can_send_data_calendar:
            return render_admin_dashboard(admin, users, error="Seçilen kullanıcı için veri gönderim yetkisi kapalı.")

        if not target_user.telegram_bot_token or not target_user.telegram_chat_id:
            return render_admin_dashboard(admin, users, error="Hedef kullanıcının Telegram bilgileri eksik.")

        frame_path = get_content_frame_path(target_user, card_type)
        if not frame_path:
            return render_admin_dashboard(admin, users, error=f"Hedef kullanıcının {card_type_label(card_type)} frame dosyası eksik.")

        content_image_path = save_uploaded_file(content_image, f"admin_{card_type}_content") if content_image and content_image.filename else ""

        if card_type == "news":
            send_news_bundle(
                title=title,
                body=body,
                frame_path=frame_path,
                logo_path=target_user.logo_path or "",
                footer_text=footer_for_user(target_user),
                content_image_path=content_image_path,
                token=target_user.telegram_bot_token,
                chat_id=target_user.telegram_chat_id,
            )
        else:
            send_data_bundle(
                title=title,
                body=body,
                frame_path=frame_path,
                logo_path=target_user.logo_path or "",
                footer_text=footer_for_user(target_user),
                content_image_path=content_image_path,
                token=target_user.telegram_bot_token,
                chat_id=target_user.telegram_chat_id,
            )

        return render_admin_dashboard(
            admin,
            users,
            success=f"{target_user.display_name or target_user.username} adına {card_type_label(card_type)} kartı gönderildi.",
        )

    except PermissionError as e:
        return HTMLResponse(str(e), status_code=403)
    except Exception as e:
        return render_admin_dashboard(admin, users, error=f"Hata: {e}")