$ErrorActionPreference = "Stop"

Set-Location "C:\Users\ALI\Desktop\elliott_web"

New-Item -ItemType Directory -Force app | Out-Null
New-Item -ItemType Directory -Force app\services | Out-Null
New-Item -ItemType Directory -Force app\templates | Out-Null
New-Item -ItemType Directory -Force app\static | Out-Null
New-Item -ItemType Directory -Force uploads | Out-Null

@'
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./elliott_v2.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
'@ | Set-Content app\database.py -Encoding UTF8

@'
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="member")
    logo_path = Column(String(255), nullable=True)
    telegram_bot_token = Column(String(255), nullable=True)
    telegram_chat_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    analyses = relationship("Analysis", back_populates="user", cascade="all, delete-orphan")


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    symbol = Column(String(50), nullable=True)
    image_path = Column(String(255), nullable=True)
    current_price = Column(Float, nullable=False)
    analysis_text = Column(Text, nullable=False)
    signal = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="analyses")
'@ | Set-Content app\models.py -Encoding UTF8

@'
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
'@ | Set-Content app\auth.py -Encoding UTF8

@'
from typing import Tuple


def generate_analysis(symbol: str, current_price: float, image_path: str | None = None) -> Tuple[str, str]:
    symbol_name = symbol.strip().upper() if symbol else "ENSTRUMAN"

    if current_price <= 0:
        return "Gecersiz fiyat verisi nedeniyle analiz uretilemedi.", "NO SIGNAL"

    if current_price < 100:
        signal = "BUY"
        analysis_text = (
            f"{symbol_name} icin girilen {current_price:.4f} fiyati dusuk bolge olarak degerlendirildi. "
            "Mevcut gorunumde alim yonlu toparlanma ihtimali one cikiyor. "
            "Destek alanindan tepki olusmasi halinde yukari yonlu hareketin guc kazanmasi beklenebilir. "
            "Yine de islem oncesinde kisa vadeli teyit alinmasi daha saglikli olacaktir."
        )
    elif current_price > 200:
        signal = "SELL"
        analysis_text = (
            f"{symbol_name} icin girilen {current_price:.4f} fiyati yuksek bolge olarak degerlendirildi. "
            "Bu yapi icinde satis baskisinin devam etme ihtimali artmis gorunuyor. "
            "Direnc cevresinde zayiflama olusursa asagi yonlu duzeltme senaryosu one cikabilir. "
            "Kesin islem karari oncesinde fiyat davranisinin yeniden teyit edilmesi onerilir."
        )
    else:
        signal = "HOLD"
        analysis_text = (
            f"{symbol_name} icin girilen {current_price:.4f} fiyati notr bolgede bulunuyor. "
            "Su an icin net bir kirilim veya guclu yon teyidi olusmadigi icin bekle-gor yaklasimi daha uygun. "
            "Fiyatin destek ya da direnc bolgelerine yaklasmasi halinde daha net senaryolar uretilebilir."
        )

    if image_path:
        analysis_text += " Yuklenen grafik gorseli analiz kaydina eklendi."

    return analysis_text, signal
'@ | Set-Content app\services\ai_service.py -Encoding UTF8

@'
import os
import shutil
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from .auth import hash_password, verify_password
from .database import Base, engine, get_db
from .models import Analysis, User
from .services.ai_service import generate_analysis

load_dotenv()

app = FastAPI(title="Elliott AI Web")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "elliott-ai-secret"),
    same_site="lax",
    https_only=False,
)

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"
UPLOAD_DIR = BASE_DIR / "uploads"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

Base.metadata.create_all(bind=engine)

app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


def get_current_user(request: Request, db: Session):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


def require_login(request: Request, db: Session):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def require_admin(request: Request, db: Session):
    user = require_login(request, db)
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def save_uploaded_file(upload: UploadFile):
    ext = Path(upload.filename).suffix.lower() if upload.filename else ""
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="Only image files allowed")

    filename = f"{uuid.uuid4().hex}{ext}"
    full_path = UPLOAD_DIR / filename

    with open(full_path, "wb") as f:
        shutil.copyfileobj(upload.file, f)

    return f"/uploads/{filename}"


@app.on_event("startup")
def startup_seed_admin():
    db = next(get_db())
    try:
        admin_exists = db.query(User).filter(User.username == "admin").first()
        if not admin_exists:
            admin_user = User(
                username="admin",
                password_hash=hash_password("123456"),
                role="super_admin",
            )
            db.add(admin_user)
            db.commit()
    finally:
        db.close()


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
    current_user = get_current_user(request, db)
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username.strip()).first()

    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Kullanici adi veya sifre hatali."},
            status_code=400,
        )

    request.session["user_id"] = user.id
    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)

    last_analyses = (
        db.query(Analysis)
        .filter(Analysis.user_id == user.id)
        .order_by(Analysis.created_at.desc())
        .limit(5)
        .all()
    )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "last_analyses": last_analyses,
            "error": None,
        },
    )


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    symbol: str = Form(""),
    current_price: float = Form(...),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    user = require_login(request, db)

    symbol = symbol.strip() if symbol else ""

    if current_price <= 0:
        last_analyses = (
            db.query(Analysis)
            .filter(Analysis.user_id == user.id)
            .order_by(Analysis.created_at.desc())
            .limit(5)
            .all()
        )
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "user": user,
                "last_analyses": last_analyses,
                "error": "Anlik fiyat 0'dan buyuk olmalidir.",
            },
            status_code=400,
        )

    image_path = None
    if image and image.filename:
        image_path = save_uploaded_file(image)

    analysis_text, signal = generate_analysis(symbol=symbol, current_price=current_price, image_path=image_path)

    new_analysis = Analysis(
        user_id=user.id,
        symbol=symbol if symbol else None,
        image_path=image_path,
        current_price=current_price,
        analysis_text=analysis_text,
        signal=signal,
    )
    db.add(new_analysis)
    db.commit()
    db.refresh(new_analysis)

    return templates.TemplateResponse(
        "result.html",
        {"request": request, "user": user, "analysis": new_analysis},
    )


@app.get("/history", response_class=HTMLResponse)
def history(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)

    analyses = (
        db.query(Analysis)
        .filter(Analysis.user_id == user.id)
        .order_by(Analysis.created_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        "history.html",
        {"request": request, "user": user, "analyses": analyses},
    )


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, db: Session = Depends(get_db)):
    admin_user = require_admin(request, db)
    users = db.query(User).order_by(User.created_at.desc()).all()

    return templates.TemplateResponse(
        "admin.html",
        {"request": request, "user": admin_user, "users": users, "message": None},
    )


@app.post("/admin/users", response_class=HTMLResponse)
def admin_create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form("member"),
    db: Session = Depends(get_db),
):
    admin_user = require_admin(request, db)
    users = db.query(User).order_by(User.created_at.desc()).all()

    username = username.strip()
    role = role.strip()

    if not username:
        return templates.TemplateResponse(
            "admin.html",
            {"request": request, "user": admin_user, "users": users, "message": "Kullanici adi bos birakilamaz."},
            status_code=400,
        )

    if len(password) < 4:
        return templates.TemplateResponse(
            "admin.html",
            {"request": request, "user": admin_user, "users": users, "message": "Sifre en az 4 karakter olmali."},
            status_code=400,
        )

    if role not in {"member", "super_admin"}:
        role = "member"

    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        return templates.TemplateResponse(
            "admin.html",
            {"request": request, "user": admin_user, "users": users, "message": "Bu kullanici adi zaten kayitli."},
            status_code=400,
        )

    new_user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
    )
    db.add(new_user)
    db.commit()

    users = db.query(User).order_by(User.created_at.desc()).all()

    return templates.TemplateResponse(
        "admin.html",
        {"request": request, "user": admin_user, "users": users, "message": "Kullanici basariyla olusturuldu."},
    )
'@ | Set-Content app\main.py -Encoding UTF8

@'
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Elliott AI | Giriş</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body class="auth-body">
    <div class="auth-bg"></div>
    <div class="auth-wrapper">
        <div class="auth-left">
            <div class="brand-badge">AI SIGNAL ENGINE</div>
            <h1>Elliott AI Platform</h1>
            <p class="auth-subtitle">
                Grafik yükle, anlık fiyatı gir, yorum ve sinyalini saniyeler içinde üret.
            </p>
            <div class="feature-list">
                <div class="feature-card"><span>⚡</span><div><h3>Hızlı Analiz</h3><p>Görsel tabanlı yorum ve sinyal üretimi</p></div></div>
                <div class="feature-card"><span>🧠</span><div><h3>AI Destekli</h3><p>Kurala dayalı yorum + gelişmiş çıktı yapısı</p></div></div>
                <div class="feature-card"><span>🔐</span><div><h3>Üyeye Özel Alan</h3><p>Her kullanıcı yalnızca kendi verisini görür</p></div></div>
            </div>
        </div>

        <div class="auth-right">
            <div class="auth-card">
                <div class="logo-circle">EA</div>
                <h2>Panele Giriş Yap</h2>
                <p class="muted center">Yetkili hesap bilgilerin ile devam et</p>

                {% if error %}
                    <div class="alert error">{{ error }}</div>
                {% endif %}

                <form method="post" action="/login" class="auth-form">
                    <label>Kullanıcı Adı</label>
                    <input type="text" name="username" placeholder="Kullanıcı adın" required>

                    <label>Şifre</label>
                    <input type="password" name="password" placeholder="Şifren" required>

                    <button type="submit" class="btn btn-primary">Giriş Yap</button>
                </form>
            </div>
        </div>
    </div>
</body>
</html>
'@ | Set-Content app\templates\login.html -Encoding UTF8

@'
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Elliott AI | Dashboard</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body class="panel-body">
    <div class="panel-layout">
        <aside class="sidebar">
            <div class="sidebar-brand">
                <div class="logo-circle small">EA</div>
                <div>
                    <h2>Elliott AI</h2>
                    <span>Signal Platform</span>
                </div>
            </div>

            <nav class="sidebar-nav">
                <a class="nav-item active" href="/dashboard">Dashboard</a>
                <a class="nav-item" href="/history">Geçmiş Analizler</a>
                {% if user.role == "super_admin" %}
                    <a class="nav-item" href="/admin">Admin Panel</a>
                {% endif %}
                <a class="nav-item danger" href="/logout">Çıkış</a>
            </nav>

            <div class="sidebar-footer glass-card">
                <p class="tiny-label">OTURUM</p>
                <h4>{{ user.username }}</h4>
                <span class="role-badge">{{ user.role }}</span>
            </div>
        </aside>

        <main class="main-content">
            <header class="top-header glass-card">
                <div>
                    <p class="tiny-label">HOŞ GELDİN</p>
                    <h1>Analiz Merkezi</h1>
                </div>
                <div class="header-actions">
                    <a class="btn btn-secondary" href="/history">Geçmiş</a>
                    {% if user.role == "super_admin" %}
                        <a class="btn btn-primary" href="/admin">Admin</a>
                    {% endif %}
                </div>
            </header>

            <section class="content-grid">
                <div class="glass-card form-card">
                    <div class="card-head">
                        <div>
                            <p class="tiny-label">YENİ İŞLEM</p>
                            <h2>Analiz Oluştur</h2>
                        </div>
                    </div>

                    {% if error %}
                        <div class="alert error">{{ error }}</div>
                    {% endif %}

                    <form method="post" action="/analyze" enctype="multipart/form-data" class="modern-form">
                        <div class="form-row">
                            <div class="field">
                                <label>Sembol</label>
                                <input type="text" name="symbol" placeholder="Örn: XAUUSD, BTCUSD, EURUSD">
                            </div>
                            <div class="field">
                                <label>Anlık Fiyat</label>
                                <input type="number" step="any" name="current_price" placeholder="Örn: 2328.45" required>
                            </div>
                        </div>

                        <div class="field">
                            <label>Grafik Görseli</label>
                            <input type="file" name="image" accept="image/*">
                        </div>

                        <div class="upload-hint">
                            Grafik görseli yükleyebilir, anlık fiyatı manuel girerek daha doğru sinyal oluşturabilirsin.
                        </div>

                        <button type="submit" class="btn btn-primary wide">Analiz Üret</button>
                    </form>
                </div>

                <div class="glass-card side-info-card">
                    <p class="tiny-label">SON KAYITLAR</p>
                    <h2>Geçmiş Özet</h2>
                    {% if last_analyses %}
                        {% for item in last_analyses %}
                            <div class="mini-step">
                                <span>•</span>
                                <div>
                                    <h4>{{ item.symbol or "Sembol yok" }} - {{ item.signal }}</h4>
                                    <p>{{ item.current_price }}</p>
                                </div>
                            </div>
                        {% endfor %}
                    {% else %}
                        <div class="empty-state">
                            <h3>Henüz analiz yok</h3>
                            <p>İlk analizi oluşturduğunda burada görünecek.</p>
                        </div>
                    {% endif %}
                </div>
            </section>
        </main>
    </div>
</body>
</html>
'@ | Set-Content app\templates\dashboard.html -Encoding UTF8

@'
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Elliott AI | Sonuç</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body class="panel-body">
    <div class="panel-layout">
        <aside class="sidebar">
            <div class="sidebar-brand">
                <div class="logo-circle small">EA</div>
                <div>
                    <h2>Elliott AI</h2>
                    <span>Signal Platform</span>
                </div>
            </div>

            <nav class="sidebar-nav">
                <a class="nav-item" href="/dashboard">Dashboard</a>
                <a class="nav-item" href="/history">Geçmiş Analizler</a>
                {% if user.role == "super_admin" %}
                    <a class="nav-item" href="/admin">Admin Panel</a>
                {% endif %}
                <a class="nav-item danger" href="/logout">Çıkış</a>
            </nav>
        </aside>

        <main class="main-content">
            <header class="top-header glass-card">
                <div>
                    <p class="tiny-label">SONUÇ</p>
                    <h1>Analiz Çıktısı</h1>
                </div>
                <div class="header-actions">
                    <a class="btn btn-secondary" href="/dashboard">Yeni Analiz</a>
                    <a class="btn btn-primary" href="/history">Geçmiş</a>
                </div>
            </header>

            <section class="result-grid">
                <div class="glass-card hero-result-card">
                    <p class="tiny-label">SİNYAL</p>
                    <h2>{{ analysis.symbol or "Belirtilmedi" }}</h2>

                    <div class="result-meta">
                        <div class="metric-box">
                            <span>Fiyat</span>
                            <strong>{{ analysis.current_price }}</strong>
                        </div>
                        <div class="metric-box">
                            <span>Sinyal</span>
                            <strong class="signal-{{ analysis.signal|lower|replace(' ', '-') }}">{{ analysis.signal }}</strong>
                        </div>
                    </div>

                    <div class="analysis-box">
                        <h3>Analiz Yorumu</h3>
                        <p>{{ analysis.analysis_text }}</p>
                    </div>
                </div>

                <div class="glass-card preview-card">
                    <p class="tiny-label">GRAFİK</p>
                    <h2>Yüklenen Görsel</h2>
                    {% if analysis.image_path %}
                        <img src="{{ analysis.image_path }}" class="preview" alt="Yüklenen grafik">
                    {% else %}
                        <div class="empty-preview">Bu analiz için görsel yüklenmedi.</div>
                    {% endif %}
                </div>
            </section>
        </main>
    </div>
</body>
</html>
'@ | Set-Content app\templates\result.html -Encoding UTF8

@'
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Elliott AI | Geçmiş</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body class="panel-body">
    <div class="panel-layout">
        <aside class="sidebar">
            <div class="sidebar-brand">
                <div class="logo-circle small">EA</div>
                <div>
                    <h2>Elliott AI</h2>
                    <span>Signal Platform</span>
                </div>
            </div>

            <nav class="sidebar-nav">
                <a class="nav-item" href="/dashboard">Dashboard</a>
                <a class="nav-item active" href="/history">Geçmiş Analizler</a>
                {% if user.role == "super_admin" %}
                    <a class="nav-item" href="/admin">Admin Panel</a>
                {% endif %}
                <a class="nav-item danger" href="/logout">Çıkış</a>
            </nav>
        </aside>

        <main class="main-content">
            <header class="top-header glass-card">
                <div>
                    <p class="tiny-label">KAYITLAR</p>
                    <h1>Analiz Geçmişi</h1>
                </div>
                <div class="header-actions">
                    <a class="btn btn-primary" href="/dashboard">Yeni Analiz</a>
                </div>
            </header>

            <div class="glass-card table-card">
                {% if analyses %}
                    <table class="modern-table">
                        <thead>
                            <tr>
                                <th>Tarih</th>
                                <th>Sembol</th>
                                <th>Fiyat</th>
                                <th>Sinyal</th>
                            </tr>
                        </thead>
                        <tbody>
                        {% for item in analyses %}
                            <tr>
                                <td>{{ item.created_at }}</td>
                                <td>{{ item.symbol or "-" }}</td>
                                <td>{{ item.current_price }}</td>
                                <td><span class="table-signal signal-{{ item.signal|lower|replace(' ', '-') }}">{{ item.signal }}</span></td>
                            </tr>
                        {% endfor %}
                        </tbody>
                    </table>
                {% else %}
                    <div class="empty-state">
                        <h3>Henüz analiz kaydı yok</h3>
                        <p>İlk analizi oluşturduğunda burada listelenecek.</p>
                    </div>
                {% endif %}
            </div>
        </main>
    </div>
</body>
</html>
'@ | Set-Content app\templates\history.html -Encoding UTF8

@'
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Elliott AI | Admin</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body class="panel-body">
    <div class="panel-layout">
        <aside class="sidebar">
            <div class="sidebar-brand">
                <div class="logo-circle small">EA</div>
                <div>
                    <h2>Elliott AI</h2>
                    <span>Signal Platform</span>
                </div>
            </div>

            <nav class="sidebar-nav">
                <a class="nav-item" href="/dashboard">Dashboard</a>
                <a class="nav-item" href="/history">Geçmiş Analizler</a>
                <a class="nav-item active" href="/admin">Admin Panel</a>
                <a class="nav-item danger" href="/logout">Çıkış</a>
            </nav>
        </aside>

        <main class="main-content">
            <header class="top-header glass-card">
                <div>
                    <p class="tiny-label">YÖNETİM</p>
                    <h1>Admin Paneli</h1>
                </div>
            </header>

            {% if message %}
                <div class="alert info">{{ message }}</div>
            {% endif %}

            <section class="content-grid">
                <div class="glass-card form-card">
                    <div class="card-head">
                        <div>
                            <p class="tiny-label">KULLANICI YÖNETİMİ</p>
                            <h2>Yeni Kullanıcı Oluştur</h2>
                        </div>
                    </div>

                    <form method="post" action="/admin/users" class="modern-form">
                        <div class="field">
                            <label>Kullanıcı Adı</label>
                            <input type="text" name="username" required>
                        </div>

                        <div class="field">
                            <label>Şifre</label>
                            <input type="password" name="password" required>
                        </div>

                        <div class="field">
                            <label>Rol</label>
                            <select name="role">
                                <option value="member">member</option>
                                <option value="super_admin">super_admin</option>
                            </select>
                        </div>

                        <button type="submit" class="btn btn-primary wide">Kullanıcı Oluştur</button>
                    </form>
                </div>

                <div class="glass-card table-card">
                    <div class="card-head">
                        <div>
                            <p class="tiny-label">KULLANICILAR</p>
                            <h2>Mevcut Liste</h2>
                        </div>
                    </div>

                    <table class="modern-table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Kullanıcı Adı</th>
                                <th>Rol</th>
                                <th>Oluşturulma</th>
                            </tr>
                        </thead>
                        <tbody>
                        {% for u in users %}
                            <tr>
                                <td>{{ u.id }}</td>
                                <td>{{ u.username }}</td>
                                <td><span class="role-badge">{{ u.role }}</span></td>
                                <td>{{ u.created_at }}</td>
                            </tr>
                        {% endfor %}
                        </tbody>
                    </table>
                </div>
            </section>
        </main>
    </div>
</body>
</html>
'@ | Set-Content app\templates\admin.html -Encoding UTF8

@'
:root {
    --bg: #09111f;
    --card: rgba(18, 28, 49, 0.72);
    --card-border: rgba(255, 255, 255, 0.08);
    --text: #eef4ff;
    --muted: #9eb0cc;
    --primary: #4f7cff;
    --primary-2: #6d5efc;
    --shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
}

* { box-sizing: border-box; }
html, body {
    margin: 0;
    padding: 0;
    min-height: 100%;
    font-family: Arial, sans-serif;
    background:
        radial-gradient(circle at top left, rgba(79,124,255,0.18), transparent 30%),
        radial-gradient(circle at top right, rgba(109,94,252,0.16), transparent 28%),
        linear-gradient(180deg, #07101c 0%, #0b1424 100%);
    color: var(--text);
}
a { text-decoration: none; }
.auth-body { min-height: 100vh; overflow: hidden; position: relative; }
.auth-bg {
    position: absolute; inset: 0;
    background:
        radial-gradient(circle at 20% 20%, rgba(79,124,255,0.22), transparent 25%),
        radial-gradient(circle at 80% 10%, rgba(0,207,255,0.16), transparent 22%),
        radial-gradient(circle at 60% 80%, rgba(109,94,252,0.18), transparent 25%);
    filter: blur(20px);
}
.auth-wrapper {
    position: relative; z-index: 1; min-height: 100vh;
    display: grid; grid-template-columns: 1.1fr 0.9fr;
    gap: 30px; padding: 40px; align-items: center;
}
.auth-left h1 { font-size: 52px; line-height: 1.05; margin: 0 0 16px; }
.auth-subtitle { max-width: 640px; color: var(--muted); font-size: 18px; line-height: 1.7; margin-bottom: 28px; }
.brand-badge, .tiny-label {
    display: inline-block; padding: 8px 12px; border-radius: 999px;
    background: rgba(79,124,255,0.12); border: 1px solid rgba(79,124,255,0.28);
    color: #bdd0ff; font-size: 12px; letter-spacing: 1px; text-transform: uppercase;
}
.feature-list { display: grid; gap: 16px; max-width: 620px; }
.feature-card, .glass-card, .auth-card {
    background: var(--card); border: 1px solid var(--card-border);
    box-shadow: var(--shadow); backdrop-filter: blur(14px);
}
.feature-card {
    display: flex; gap: 16px; align-items: flex-start;
    padding: 18px 20px; border-radius: 18px;
}
.feature-card span { font-size: 24px; }
.feature-card h3 { margin: 0 0 4px; font-size: 17px; }
.feature-card p { margin: 0; color: var(--muted); }
.auth-right { display: flex; justify-content: center; }
.auth-card { width: 100%; max-width: 470px; padding: 34px; border-radius: 28px; }
.logo-circle {
    width: 68px; height: 68px; border-radius: 50%; display: grid; place-items: center;
    font-weight: 700; font-size: 24px; background: linear-gradient(135deg, var(--primary), var(--primary-2));
    box-shadow: 0 10px 30px rgba(79,124,255,0.35); margin-bottom: 16px;
}
.logo-circle.small { width: 48px; height: 48px; font-size: 18px; margin-bottom: 0; }
.auth-card h2 { margin: 0 0 8px; font-size: 30px; }
.center { text-align: center; }
.muted { color: var(--muted); }
.auth-form, .modern-form { display: flex; flex-direction: column; gap: 14px; margin-top: 18px; }
label { font-size: 14px; color: #dbe7ff; margin-bottom: 6px; }
input, select {
    width: 100%; padding: 14px 16px; border-radius: 14px; border: 1px solid rgba(255,255,255,0.08);
    outline: none; background: rgba(8, 16, 31, 0.85); color: white; font-size: 15px;
}
.btn {
    display: inline-flex; justify-content: center; align-items: center; padding: 14px 18px;
    border-radius: 14px; border: none; cursor: pointer; font-weight: 600;
}
.btn-primary { background: linear-gradient(135deg, var(--primary), var(--primary-2)); color: white; }
.btn-secondary { background: rgba(255,255,255,0.06); color: white; border: 1px solid rgba(255,255,255,0.08); }
.wide { width: 100%; }
.alert { padding: 14px 16px; border-radius: 14px; margin-top: 16px; font-size: 14px; }
.alert.error { background: rgba(255,95,122,0.12); border: 1px solid rgba(255,95,122,0.22); color: #ffb7c4; }
.alert.info { background: rgba(79,124,255,0.12); border: 1px solid rgba(79,124,255,0.22); color: #cbd9ff; margin: 0 0 20px; }
.panel-layout { display: grid; grid-template-columns: 280px 1fr; min-height: 100vh; }
.sidebar {
    padding: 24px 20px; border-right: 1px solid rgba(255,255,255,0.06);
    background: rgba(5, 10, 20, 0.45); backdrop-filter: blur(12px);
}
.sidebar-brand { display: flex; align-items: center; gap: 14px; margin-bottom: 34px; }
.sidebar-brand h2 { margin: 0; font-size: 20px; }
.sidebar-brand span { color: var(--muted); font-size: 13px; }
.sidebar-nav { display: flex; flex-direction: column; gap: 10px; }
.nav-item {
    padding: 14px 16px; border-radius: 14px; color: #dbe7ff;
    background: transparent; border: 1px solid transparent;
}
.nav-item:hover, .nav-item.active { background: rgba(79,124,255,0.10); border-color: rgba(79,124,255,0.22); }
.nav-item.danger:hover { background: rgba(255,95,122,0.10); border-color: rgba(255,95,122,0.22); }
.sidebar-footer { margin-top: 24px; padding: 18px; border-radius: 18px; }
.sidebar-footer h4 { margin: 10px 0 8px; }
.role-badge {
    display: inline-block; padding: 6px 10px; border-radius: 999px;
    background: rgba(79,124,255,0.12); border: 1px solid rgba(79,124,255,0.22);
    color: #d1ddff; font-size: 12px;
}
.main-content { padding: 26px; }
.top-header {
    padding: 24px; border-radius: 24px; margin-bottom: 22px;
    display: flex; justify-content: space-between; align-items: center;
}
.top-header h1 { margin: 8px 0 0; font-size: 34px; }
.header-actions { display: flex; gap: 12px; }
.content-grid, .result-grid { display: grid; grid-template-columns: 1.25fr 0.75fr; gap: 20px; }
.form-card, .side-info-card, .preview-card, .hero-result-card, .table-card { border-radius: 24px; padding: 24px; }
.card-head { margin-bottom: 20px; }
.card-head h2, .side-info-card h2, .preview-card h2, .hero-result-card h2, .table-card h2 { margin: 8px 0 0; font-size: 28px; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.field { display: flex; flex-direction: column; }
.upload-hint {
    margin-top: 6px; margin-bottom: 8px; padding: 14px 16px; border-radius: 14px;
    color: var(--muted); background: rgba(255,255,255,0.04); border: 1px dashed rgba(255,255,255,0.08);
}
.mini-step {
    display: flex; gap: 14px; align-items: flex-start; padding: 14px 0;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}
.mini-step:last-child { border-bottom: none; }
.mini-step span {
    width: 34px; height: 34px; border-radius: 50%; display: grid; place-items: center;
    background: linear-gradient(135deg, var(--primary), var(--primary-2)); font-weight: 700; flex-shrink: 0;
}
.mini-step h4 { margin: 0 0 6px; }
.mini-step p { margin: 0; color: var(--muted); line-height: 1.5; }
.result-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 18px; margin-bottom: 22px; }
.metric-box {
    padding: 18px; border-radius: 18px; background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.06);
}
.metric-box span { display: block; color: var(--muted); margin-bottom: 8px; }
.metric-box strong { font-size: 24px; }
.analysis-box {
    padding: 20px; border-radius: 18px; background: rgba(7, 14, 27, 0.72);
    border: 1px solid rgba(255,255,255,0.06);
}
.analysis-box h3 { margin-top: 0; }
.analysis-box p { margin-bottom: 0; color: #dbe6fb; line-height: 1.7; }
.preview { width: 100%; border-radius: 18px; margin-top: 16px; border: 1px solid rgba(255,255,255,0.08); }
.empty-preview, .empty-state {
    padding: 34px; border-radius: 18px; text-align: center; color: var(--muted);
    background: rgba(255,255,255,0.04); border: 1px dashed rgba(255,255,255,0.10);
}
.modern-table { width: 100%; border-collapse: collapse; }
.modern-table th, .modern-table td { text-align: left; padding: 16px 14px; border-bottom: 1px solid rgba(255,255,255,0.06); }
.modern-table th { color: #c6d6f3; font-weight: 600; font-size: 14px; }
.modern-table td { color: #edf3ff; }
.table-signal, .signal-buy, .signal-sell, .signal-hold, .signal-no-signal {
    display: inline-flex; padding: 7px 12px; border-radius: 999px; font-size: 13px; font-weight: 600;
}
.signal-buy { color: #bff5dd; background: rgba(24,195,126,0.14); border: 1px solid rgba(24,195,126,0.22); }
.signal-sell { color: #ffc1cb; background: rgba(255,95,122,0.14); border: 1px solid rgba(255,95,122,0.22); }
.signal-hold, .signal-no-signal { color: #ffe0b1; background: rgba(255,181,71,0.14); border: 1px solid rgba(255,181,71,0.22); }

@media (max-width: 1100px) {
    .auth-wrapper, .panel-layout, .content-grid, .result-grid, .form-row { grid-template-columns: 1fr; }
    .sidebar { display: none; }
    .main-content { padding: 16px; }
    .top-header { flex-direction: column; gap: 16px; align-items: flex-start; }
    .auth-left h1 { font-size: 38px; }
}
'@ | Set-Content app\static\style.css -Encoding UTF8

@'
SECRET_KEY=elliott-ai-super-secret-key
'@ | Set-Content .env -Encoding UTF8

Write-Host "Tum dosyalar yeniden yazildi." -ForegroundColor Green