import os
from pathlib import Path

CONTENT_DIR = Path(os.getenv("CONTENT_DIR", "/content"))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/talkshow.db")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
COOKIE_MAX_AGE = int(os.getenv("COOKIE_MAX_AGE", "86400"))
