from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(20), default="admin")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Theme(Base):
    __tablename__ = "themes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    theme_file = Column(String(300), nullable=False)
    icon = Column(String(20), default="🚀")
    tags = Column(String(300), default="")
    presentation_count = Column(Integer, default=0)
    visible = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ShareLink(Base):
    __tablename__ = "share_links"
    id = Column(Integer, primary_key=True, autoincrement=True)
    theme_id = Column(Integer, ForeignKey("themes.id"), nullable=False)
    token = Column(String(64), unique=True, nullable=False, index=True)
    password = Column(String(128), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    theme = relationship("Theme")
    creator = relationship("User")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    detail = Column(Text, default="")
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
