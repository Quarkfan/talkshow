import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .config import CONTENT_DIR, SECRET_KEY, COOKIE_MAX_AGE
from .database import engine, Base, SessionLocal, get_db
from .init_db import init_db
from .models import ShareLink, Theme, AuditLog, User, ContentRule, ShareFileRule
from .utils import resolve_file_theme
from .auth import hash_password
from .routes import auth, themes, shares, audit, content_rules, share_file_rules


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
    # Initialize backup repo in background (non-blocking)
    import threading
    from .backup import init_backup_repo
    threading.Thread(target=init_backup_repo, daemon=True).start()
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
app.include_router(content_rules.router)
app.include_router(share_file_rules.router)

# Serve uploaded logos
LOGO_DIR = Path(__file__).parent.parent / "data" / "logos"


@app.get("/logos/{filename}")
async def serve_logo(filename: str):
    if not re.match(r'^[\w\-\.]+$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = LOGO_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Logo not found")
    return FileResponse(str(path))


# Serve frontend static assets (no cache so dev changes take effect immediately)
FRONTEND = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND / "static"), html=False), name="static")

# Disable caching for static files
from starlette.middleware.base import BaseHTTPMiddleware

class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        # Also disable caching for HTML pages so JS version params take effect
        if request.url.path in ("/", "/login", "/console", "/blocked", "/locked") or request.url.path.startswith("/s/"):
            response.headers["Cache-Control"] = "no-store, must-revalidate"
        return response

app.add_middleware(NoCacheStaticMiddleware)

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


@app.get("/blocked")
async def blocked_page():
    return FileResponse(str(FRONTEND / "blocked.html"))


@app.get("/locked")
async def locked_page():
    return FileResponse(str(FRONTEND / "locked.html"))


# --- Protected content serving (admin only) ---


@app.get("/content/{path:path}")
async def serve_content(path: str, request: Request):
    from urllib.parse import unquote

    user_id = request.session.get("user_id")
    if user_id:
        # Admin: serve directly
        clean_path = unquote(unquote(path))
        db = SessionLocal()
        ip = request.client.host if request.client else None
        try:
            full_path = CONTENT_DIR / clean_path
            if not full_path.exists() or not full_path.is_file():
                raise HTTPException(status_code=404, detail="File not found")
            db.add(AuditLog(action="content_access", detail=f'{{"path":"{path}","user_id":{user_id}}}', ip_address=ip))
            db.commit()
            return FileResponse(str(full_path))
        finally:
            db.close()

    # Anonymous: sub-page navigation from /t/{slug} or direct access
    # Permission: ContentRule → Theme.accessible
    clean_path = unquote(unquote(path))
    db = SessionLocal()
    ip = request.client.host if request.client else None
    try:
        full_path = CONTENT_DIR / clean_path
        if not full_path.exists() or not full_path.is_file():
            db.add(AuditLog(action="content_404", detail=f'{{"path":"{path}"}}', ip_address=ip))
            db.commit()
            raise HTTPException(status_code=404, detail="Not found")

        # 1. ContentRule(public=False) — global block
        content_rule = db.query(ContentRule).filter(ContentRule.path == clean_path).first()
        if content_rule and not content_rule.public:
            db.add(AuditLog(action="content_blocked", detail=f'{{"path":"{clean_path}","reason":"file_hidden"}}', ip_address=ip))
            db.commit()
            return RedirectResponse(url="/blocked", status_code=302)

        # 2. Theme inheritance — file belongs to a known theme
        themes = db.query(Theme).all()
        parent_theme = resolve_file_theme(clean_path, themes)
        if parent_theme:
            if not parent_theme.accessible:
                db.add(AuditLog(action="content_blocked", detail=f'{{"path":"{clean_path}","reason":"theme_not_accessible","theme":"{parent_theme.title}"}}', ip_address=ip))
                db.commit()
                return RedirectResponse(url="/blocked", status_code=302)
            db.add(AuditLog(action="content_access", detail=f'{{"path":"{clean_path}","source":"theme_inherited","theme":"{parent_theme.title}"}}', ip_address=ip))
            db.commit()
            return FileResponse(str(full_path))

        # 3. File doesn't belong to any known theme (e.g. presentations/, references/)
        #    → allow only if at least one theme is accessible (user navigated from open theme)
        if any(t.accessible for t in themes):
            db.add(AuditLog(action="content_access", detail=f'{{"path":"{clean_path}","source":"any_theme_accessible"}}', ip_address=ip))
            db.commit()
            return FileResponse(str(full_path))
        db.add(AuditLog(action="content_blocked", detail=f'{{"path":"{clean_path}","reason":"no_parent_theme"}}', ip_address=ip))
        db.commit()
        return RedirectResponse(url="/blocked", status_code=302)
    finally:
        db.close()


# --- Theme entry point (anonymous, slug-based, no real path exposure) ---


@app.get("/t/{slug}")
async def theme_entry(slug: str, request: Request):
    db = SessionLocal()
    ip = request.client.host if request.client else None
    try:
        theme = db.query(Theme).filter(Theme.slug == slug).first()
        if not theme or not theme.visible:
            raise HTTPException(status_code=404, detail="Not found")
        if not theme.accessible:
            return RedirectResponse(url="/blocked", status_code=302)

        full_path = CONTENT_DIR / theme.theme_file
        if not full_path.exists() or not full_path.is_file():
            raise HTTPException(status_code=404, detail="Not found")

        # Global ContentRule check
        content_rule = db.query(ContentRule).filter(ContentRule.path == theme.theme_file).first()
        if content_rule and not content_rule.public:
            db.add(AuditLog(action="content_blocked", detail=f'{{"path":"{theme.theme_file}","reason":"file_hidden"}}', ip_address=ip))
            db.commit()
            return RedirectResponse(url="/blocked", status_code=302)

        # Serve with <base> tag so relative links resolve through /content/
        # (sub-page navigation hits /content/{sub_path}, checked against theme.accessible + ContentRule)
        return _serve_with_base(str(full_path), base_href="/content/")
    finally:
        db.close()


def _serve_with_base(file_path: str, base_href: str | None) -> Response:
    """Serve an HTML file with optional <base> tag injected for relative link resolution."""
    content = Path(file_path).read_bytes()
    if base_href:
        content_str = content.decode("utf-8")
        base_tag = f'<base href="{base_href}">'
        content_str = re.sub(r'(<head[^>]*>)', rf'\1{base_tag}', content_str, count=1, flags=re.IGNORECASE)
        return Response(content=content_str.encode("utf-8"), media_type="text/html")
    return FileResponse(file_path)


# --- Share link entry point (no cookie, HTML <base> injection) ---


@app.get("/s/{token}")
async def share_access(token: str, request: Request, password: str | None = None):
    db = SessionLocal()
    ip = request.client.host if request.client else None
    try:
        link = db.query(ShareLink).filter(ShareLink.token == token).first()
        if not link or not link.active:
            raise HTTPException(status_code=404, detail="Invalid or revoked link")
        expires_at = link.expires_at
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at and expires_at < datetime.now(timezone.utc):
            link.active = False
            db.commit()
            raise HTTPException(status_code=410, detail="Expired")
        if link.password and password != link.password:
            theme = db.query(Theme).filter(Theme.id == link.theme_id).first()
            return _share_password_page(token, theme.title if theme else "Theme")

        theme = db.query(Theme).filter(Theme.id == link.theme_id).first()
        db.add(AuditLog(
            action="share_access",
            detail=f'{{"token":"{token[:8]}...","theme_id":{link.theme_id}}}',
            ip_address=ip
        ))
        db.commit()

        theme_path = CONTENT_DIR / theme.theme_file
        if not theme_path.exists():
            raise HTTPException(status_code=404, detail="Theme file not found")

        # Inject <base> so all relative links go through /s/{token}/file/
        return _serve_with_base(str(theme_path), base_href=f"/s/{token}/file/")
    finally:
        db.close()


@app.get("/s/{token}/file/{path:path}")
async def share_file(token: str, path: str, request: Request, password: str | None = None):
    from urllib.parse import unquote

    clean_path = unquote(unquote(path))
    db = SessionLocal()
    ip = request.client.host if request.client else None
    try:
        link = db.query(ShareLink).filter(ShareLink.token == token).first()
        if not link or not link.active:
            raise HTTPException(status_code=404, detail="Invalid or revoked link")

        # Check expiry
        if link.expires_at:
            expires_at = link.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < datetime.now(timezone.utc):
                link.active = False
                db.commit()
                raise HTTPException(status_code=410, detail="Expired")

        # Check password (via URL param or session)
        if link.password:
            pw = password or request.query_params.get("password")
            session_pw = request.session.get(f"share_pw_{token}")
            if pw != link.password and session_pw != link.password:
                theme = db.query(Theme).filter(Theme.id == link.theme_id).first()
                return _share_password_page(token, theme.title if theme else "Theme", password_in_url=pw)

        # Remember password in session for subsequent file requests
        if link.password and password:
            request.session[f"share_pw_{token}"] = password

        full_path = CONTENT_DIR / clean_path
        if not full_path.exists() or not full_path.is_file():
            raise HTTPException(status_code=404, detail="Not found")

        # === Permission checks ===

        # 1. ContentRule(public=False) — global block, highest priority
        content_rule = db.query(ContentRule).filter(ContentRule.path == clean_path).first()
        if content_rule and not content_rule.public:
            db.add(AuditLog(action="content_blocked", detail=f'{{"path":"{clean_path}","reason":"file_hidden"}}', ip_address=ip))
            db.commit()
            return RedirectResponse(url="/blocked", status_code=302)

        # 2. ShareFileRule — per-share per-file rule
        share_file_rule = db.query(ShareFileRule).filter(
            ShareFileRule.share_id == link.id,
            ShareFileRule.path == clean_path,
        ).first()
        if share_file_rule:
            if share_file_rule.public:
                db.add(AuditLog(action="content_access", detail=f'{{"path":"{clean_path}","source":"share_file_rule","share_id":{link.id}}}', ip_address=ip))
                db.commit()
                return FileResponse(str(full_path))
            else:
                db.add(AuditLog(action="content_blocked", detail=f'{{"path":"{clean_path}","reason":"share_file_rule_deny","share_id":{link.id}}}', ip_address=ip))
                db.commit()
                return RedirectResponse(url="/blocked", status_code=302)

        # 3. ShareLink.allow_content
        if not link.allow_content:
            db.add(AuditLog(action="content_blocked", detail=f'{{"path":"{clean_path}","reason":"share_content_disabled"}}', ip_address=ip))
            db.commit()
            return RedirectResponse(url="/locked", status_code=302)

        # 4. File belongs to share's theme — allow
        theme = db.query(Theme).filter(Theme.id == link.theme_id).first()
        if theme and (clean_path == theme.theme_file or resolve_file_theme(clean_path, [theme])):
            db.add(AuditLog(action="content_access", detail=f'{{"path":"{clean_path}","source":"share","token":"{token[:8]}..."}}', ip_address=ip))
            db.commit()
            return FileResponse(str(full_path))

        # Fallback: file not owned by any specific theme (e.g. presentations/)
        # → use share's own theme's accessible setting
        if theme and theme.accessible:
            db.add(AuditLog(action="content_access", detail=f'{{"path":"{clean_path}","source":"share_theme_accessible","theme_id":{link.theme_id}}}', ip_address=ip))
            db.commit()
            return FileResponse(str(full_path))

        db.add(AuditLog(action="content_blocked", detail=f'{{"path":"{clean_path}","reason":"not_in_share"}}', ip_address=ip))
        db.commit()
        return RedirectResponse(url="/blocked", status_code=302)
    finally:
        db.close()


def _share_password_page(token: str, title: str, password_in_url: str | None = None) -> FileResponse:
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
