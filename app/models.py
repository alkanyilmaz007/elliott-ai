from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    # giriş
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user", nullable=False)

    # şirket / marka bilgisi
    company_name = Column(String, default="", nullable=False)
    display_name = Column(String, default="", nullable=False)
    logo_path = Column(String, default="", nullable=False)

    # telegram branding frame'leri
    frame_main_path = Column(String, default="", nullable=False)
    frame_fractal_path = Column(String, default="", nullable=False)
    frame_news_path = Column(String, default="", nullable=False)
    frame_data_path = Column(String, default="", nullable=False)

    # telegram ayarları
    telegram_bot_token = Column(Text, default="", nullable=False)
    telegram_chat_id = Column(String, default="", nullable=False)

    # üyelik / yetki
    is_active = Column(Boolean, default=True, nullable=False)
    can_send_analysis = Column(Boolean, default=True, nullable=False)
    can_send_signal = Column(Boolean, default=True, nullable=False)
    can_send_news = Column(Boolean, default=False, nullable=False)
    can_send_data_calendar = Column(Boolean, default=False, nullable=False)

    subscription_plan = Column(String, default="standard", nullable=False)
    subscription_end_date = Column(DateTime(timezone=True), nullable=True)

    # audit
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )