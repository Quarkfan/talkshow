from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
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
    logo_bg = Column(String(20), default="")       # CSS color for logo background (PNG transparency)
    tags = Column(String(300), default="")
    presentation_count = Column(Integer, default=0)
    visible = Column(Boolean, default=True)      # 主页是否显示卡片
    accessible = Column(Boolean, default=True)   # 内容是否可访问（文件级继承自这个）
    is_copy = Column(Boolean, default=False)     # 是否为复制的主题（复制的才允许删除）
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ShareLink(Base):
    __tablename__ = "share_links"
    id = Column(Integer, primary_key=True, autoincrement=True)
    theme_id = Column(Integer, ForeignKey("themes.id"), nullable=False)
    token = Column(String(64), unique=True, nullable=False, index=True)
    password = Column(String(128), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True)
    allow_content = Column(Boolean, default=True)  # 是否允许通过分享访问第三层内容
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


class ContentRule(Base):
    __tablename__ = "content_rules"
    id = Column(Integer, primary_key=True, autoincrement=True)
    path = Column(String(500), unique=True, nullable=False, index=True)
    theme_id = Column(Integer, ForeignKey("themes.id"), nullable=True, index=True)
    public = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ShareFileRule(Base):
    __tablename__ = "share_file_rules"
    id = Column(Integer, primary_key=True, autoincrement=True)
    share_id = Column(Integer, ForeignKey("share_links.id"), nullable=False, index=True)
    path = Column(String(500), nullable=False, index=True)
    public = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint('share_id', 'path'),)
    share = relationship("ShareLink")
