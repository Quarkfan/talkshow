"""Seed admin user. Run once: python seed_admin.py"""
import sys
import os

# Ensure we can import backend modules
sys.path.insert(0, os.path.dirname(__file__))

from backend.database import engine, SessionLocal, Base
from backend.models import User
from backend.auth import hash_password

USERNAME = os.getenv("ADMIN_USERNAME", "admin")
PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    existing = db.query(User).filter(User.username == USERNAME).first()
    if existing:
        print(f"[seed_admin] User '{USERNAME}' already exists, skipping.")
        db.close()
        return
    user = User(username=USERNAME, password_hash=hash_password(PASSWORD), role="admin")
    db.add(user)
    db.commit()
    print(f"[seed_admin] Created admin user: {USERNAME} / {PASSWORD}")
    print("[seed_admin] Please change the password in production!")
    db.close()


if __name__ == "__main__":
    seed()
