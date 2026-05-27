import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import CONTENT_DIR, SECRET_KEY, COOKIE_MAX_AGE
from .database import engine, Base, SessionLocal, get_db
from .init_db import init_db
from .models import ShareLink, Theme, AuditLog, User
from .auth import hash_password
from .routes import auth, themes, shares, audit


def _seed_admin():
    """Create default admin user if not exists."""
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "changeme")
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            return
        user = User(username=username, password_hash=hash_password(password), role="admin")
        db.add(user)
        db.commit()
        print(f"[talkshow] Admin user created: {username}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _seed_admin()
    app.state.content_dir = CONTENT_DIR
    init_db(CONTENT_DIR)
    yield


app = FastAPI(title="talkshow", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    max_age=COOKIE_MAX_AGE,
    https_only=False,
)

# API routes
app.include_router(auth.router)
app.include_router(themes.router)
app.include_router(shares.router)
app.include_router(audit.router)

# Serve frontend static assets
FRONTEND = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND / "static")), name="static")

# --- Page routes ---

@app.get("/")
async def index():
    return FileResponse(str(FRONTEND / "index.html"))


@app.get("/login")
async def login_page():
    return FileResponse(str(FRONTEND / "login.html"))


@app.get("/console")
async def console_page(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login", status_code=302)
    return FileResponse(str(FRONTEND / "console.html"))


# --- Protected content serving (replaces StaticFiles mount) ---

@app.get("/content/{path:path}")
async def serve_content(path: str, request: Request):
    """Serve files from talkResources with visibility checks.

    Rules:
    - Admin (logged in): access all content
    - Anonymous: if any theme is visible, access all content; otherwise block
    """
    from urllib.parse import unquote

    db = SessionLocal()
    try:
        full_path = CONTENT_DIR / unquote(path)
        if not full_path.exists() or not full_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")

        # Admin can access everything
        user_id = request.session.get("user_id")
        if user_id:
            return FileResponse(str(full_path))

        # Anonymous: check if there's at least one visible theme
        has_visible = db.query(Theme).filter(Theme.visible == True).first()
        if not has_visible:
            raise HTTPException(status_code=403, detail="No content available")

        return FileResponse(str(full_path))
    finally:
        db.close()


# --- Share link access ---

from datetime import datetime, timezone


@app.get("/s/{token}")
async def share_access(token: str, request: Request, password: str | None = None):
    db = SessionLocal()
    try:
        link = db.query(ShareLink).filter(ShareLink.token == token).first()
        if not link or not link.active:
            raise HTTPException(status_code=404, detail="Invalid or revoked link")
        expires_at = link.expires_at
        if expires_at and expires_at.tzinfo is None:
            from datetime import timezone as _tz
            expires_at = expires_at.replace(tzinfo=_tz.utc)
        if expires_at and expires_at < datetime.now(timezone.utc):
            link.active = False
            db.commit()
            raise HTTPException(status_code=410, detail="Expired")
        if link.password and password != link.password:
            # Return a password prompt page instead of the content
            theme = db.query(Theme).filter(Theme.id == link.theme_id).first()
            return _share_password_page(token, theme.title if theme else "Theme")

        theme = db.query(Theme).filter(Theme.id == link.theme_id).first()
        db.add(AuditLog(
            action="share_access",
            detail=f'{{"token":"{token[:8]}...","theme_id":{link.theme_id}}}',
            ip_address=request.client.host if request.client else None
        ))
        db.commit()

        theme_path = CONTENT_DIR / theme.theme_file
        if not theme_path.exists():
            raise HTTPException(status_code=404, detail="Theme file not found")
        return FileResponse(str(theme_path))
    finally:
        db.close()


def _share_password_page(token: str, title: str) -> FileResponse:
    """Return a simple password prompt HTML for this share link."""
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>需要密码 - {title}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display",sans-serif;background:#06090f;color:#e5eef9;display:flex;align-items:center;justify-content:center;min-height:100vh}}
.box{{background:rgba(20,26,39,.9);border:1px solid rgba(148,163,184,.14);border-radius:12px;padding:40px;text-align:center;max-width:400px;width:90%}}
h1{{font-size:1.4rem;margin-bottom:8px}}
p{{color:#9aa8bb;font-size:.85rem;margin-bottom:24px}}
input{{width:100%;padding:10px 14px;border-radius:8px;border:1px solid rgba(148,163,184,.2);background:rgba(20,26,39,.8);color:#e5eef9;font-size:1rem;margin-bottom:16px;outline:none}}
input:focus{{border-color:rgba(56,189,248,.5)}}
button{{width:100%;padding:10px;border-radius:8px;border:none;background:linear-gradient(135deg,#38bdf8,#818cf8);color:#fff;font-size:1rem;font-weight:600;cursor:pointer}}
button:hover{{opacity:.9}}
.error{{color:#f87171;font-size:.8rem;margin-top:12px;display:none}}
</style></head>
<body><div class="box">
<h1>🔒 此分享需要密码</h1>
<p>{title}</p>
<form id="form">
<input type="password" id="pw" placeholder="输入访问密码" autocomplete="off" autofocus>
<button type="submit">进入</button>
<div class="error" id="err">密码错误</div>
</form>
</div>
<script>
document.getElementById('form').onsubmit=async(e)=>{{e.preventDefault();
const pw=document.getElementById('pw').value;
const r=await fetch('/api/shares/{token}/validate',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{password:pw}})}});
if(r.ok){{window.location.href='/s/{token}?password='+pw}}else{{document.getElementById('err').style.display='block'}}}};
</script></body></html>"""
    import tempfile
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8")
    f.write(html)
    f.close()
    return FileResponse(f.name, media_type="text/html")
