import os
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Request, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Theme, AuditLog
from ..auth import require_auth, require_admin
from ..init_db import scan_content_dir

ALLOWED_MIME = {"image/png", "image/jpeg", "image/svg+xml", "image/webp", "image/gif"}
MAX_SIZE = 2 * 1024 * 1024  # 2MB

def _logo_dir() -> Path:
    return Path(__file__).parent.parent.parent / "data" / "logos"

def _logo_url(icon: str | None) -> str | None:
    if icon and icon.startswith("logo:"):
        return f"/logos/{icon[5:]}"
    return None

def _icon_for_api(icon: str | None) -> str:
    if icon and icon.startswith("logo:"):
        return ""
    return icon or ""


class ThemeUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    icon: str | None = None
    logo_bg: str = ""


router = APIRouter(prefix="/api", tags=["themes"])


@router.get("/themes/public")
async def list_public_themes(db: Session = Depends(get_db)):
    themes = db.query(Theme).filter(Theme.visible == True).all()
    return [{
        "id": t.id, "slug": t.slug, "title": t.title,
        "description": t.description, "icon": _icon_for_api(t.icon),
        "logo_url": _logo_url(t.icon),
        "logo_bg": t.logo_bg if t.logo_bg else "#141a27",
        "tags": t.tags.split(",") if t.tags else [],
        "presentation_count": t.presentation_count,
        "entry_url": f"/t/{t.slug}" if t.accessible else None,
        "accessible": t.accessible
    } for t in themes]


@router.get("/themes")
async def list_all_themes(request: Request, db: Session = Depends(get_db)):
    require_auth(request)
    themes = db.query(Theme).all()
    return [{
        "id": t.id, "slug": t.slug, "title": t.title,
        "visible": t.visible, "accessible": t.accessible,
        "is_copy": t.is_copy,
        "theme_file": t.theme_file,
        "icon": _icon_for_api(t.icon),
        "logo_url": _logo_url(t.icon),
        "logo_bg": t.logo_bg if t.logo_bg else "#141a27",
        "tags": t.tags,
        "description": t.description,
        "presentation_count": t.presentation_count,
        "created_at": t.created_at.isoformat()
    } for t in themes]


@router.patch("/themes/{theme_id}/visibility")
async def toggle_visibility(theme_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_admin(require_auth(request))
    theme = db.query(Theme).filter(Theme.id == theme_id).first()
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    theme.visible = not theme.visible
    db.add(AuditLog(
        user_id=user.id, action="theme_toggle_visibility",
        detail=f'{{"theme_id":{theme_id},"visible":{theme.visible}}}'
    ))
    db.commit()
    from ..backup import schedule_backup
    schedule_backup()
    return {"id": theme.id, "visible": theme.visible}


@router.patch("/themes/{theme_id}/accessible")
async def toggle_accessible(theme_id: int, request: Request, db: Session = Depends(get_db)):
    """Toggle whether theme content is accessible (files inherit from this)."""
    user = require_admin(require_auth(request))
    theme = db.query(Theme).filter(Theme.id == theme_id).first()
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    theme.accessible = not theme.accessible
    db.add(AuditLog(
        user_id=user.id, action="theme_toggle_accessible",
        detail=f'{{"theme_id":{theme_id},"accessible":{theme.accessible}}}'
    ))
    db.commit()
    from ..backup import schedule_backup
    schedule_backup()
    return {"id": theme.id, "accessible": theme.accessible}


@router.post("/themes/rescan")
async def rescan_themes(request: Request, db: Session = Depends(get_db)):
    """Git pull from remote then rescan content directory."""
    import subprocess
    user = require_admin(require_auth(request))

    # Configure SSH for git
    import os as _os
    ssh_cmd = "ssh -i /root/.ssh/id_ed25519_github -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/root/.ssh/known_hosts"

    git_pull = ""
    try:
        env = _os.environ.copy()
        env["GIT_SSH_COMMAND"] = ssh_cmd
        result = subprocess.run(
            ["git", "-C", "/content", "pull", "origin", "main"],
            capture_output=True, text=True, timeout=60, env=env
        )
        git_pull = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        git_pull = "Git pull timed out"
    except Exception as e:
        git_pull = f"Git pull error: {e}"

    scan_content_dir(request.app.state.content_dir)
    db.add(AuditLog(user_id=user.id, action="rescan", detail=git_pull[:500] if git_pull else ""))
    db.commit()
    # Note: rescan does git pull but does NOT change DB content (only audit log), skip backup
    return {"ok": True, "git_pull": git_pull}


@router.post("/themes/{theme_id}/duplicate")
async def duplicate_theme(theme_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_admin(require_auth(request))
    original = db.query(Theme).filter(Theme.id == theme_id).first()
    if not original:
        raise HTTPException(status_code=404, detail="Theme not found")

    # Generate unique slug
    base_slug = original.slug
    counter = 1
    while True:
        new_slug = f"{base_slug}-{counter}"
        existing = db.query(Theme).filter(Theme.slug == new_slug).first()
        if not existing:
            break
        counter += 1

    new_theme = Theme(
        slug=new_slug,
        title=original.title,
        description=original.description,
        theme_file=original.theme_file,
        icon=original.icon,
        tags=original.tags,
        presentation_count=original.presentation_count,
        visible=False,
        accessible=True,
        is_copy=True,
    )
    db.add(new_theme)
    db.add(AuditLog(
        user_id=user.id, action="theme_duplicate",
        detail=f'{{"from_id":{theme_id},"new_slug":"{new_slug}"}}',
        ip_address=request.client.host if request.client else None
    ))
    db.commit()
    db.refresh(new_theme)
    from ..backup import schedule_backup
    schedule_backup()
    return {"id": new_theme.id, "slug": new_slug, "title": new_theme.title}


@router.delete("/themes/{theme_id}")
async def delete_theme(theme_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_admin(require_auth(request))
    theme = db.query(Theme).filter(Theme.id == theme_id).first()
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    if not theme.is_copy:
        raise HTTPException(status_code=403, detail="原始主题不允许删除，只能删除复制的主题")
    slug = theme.slug
    db.add(AuditLog(
        user_id=user.id, action="theme_delete",
        detail=f'{{"theme_id":{theme_id},"slug":"{slug}"}}',
        ip_address=request.client.host if request.client else None
    ))
    db.delete(theme)
    db.commit()
    from ..backup import schedule_backup
    schedule_backup()
    return {"ok": True, "slug": slug}


@router.patch("/themes/{theme_id}")
async def update_theme(
    theme_id: int, body: ThemeUpdate, request: Request, db: Session = Depends(get_db)
):
    user = require_admin(require_auth(request))
    theme = db.query(Theme).filter(Theme.id == theme_id).first()
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    if body.title is not None:
        theme.title = body.title
    if body.description is not None:
        theme.description = body.description
    if body.icon is not None:
        theme.icon = body.icon
    if body.logo_bg is not None and body.logo_bg != "":
        theme.logo_bg = body.logo_bg
    db.add(AuditLog(
        user_id=user.id, action="theme_update",
        detail=f'{{"theme_id":{theme_id},"updates":{body.model_dump(exclude_none=True)}}}',
        ip_address=request.client.host if request.client else None
    ))
    db.commit()
    db.refresh(theme)
    from ..backup import schedule_backup
    schedule_backup()
    return {"id": theme.id, "title": theme.title, "description": theme.description, "icon": theme.icon}


@router.post("/themes/{theme_id}/logo")
async def upload_logo(theme_id: int, request: Request, file: UploadFile, db: Session = Depends(get_db)):
    require_admin(require_auth(request))
    theme = db.query(Theme).filter(Theme.id == theme_id).first()
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")

    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {file.content_type}")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="文件大小不能超过 2MB")

    # Save file
    dir_path = _logo_dir()
    dir_path.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1] or ".png"
    safe_name = f"{theme.id}_{uuid.uuid4().hex[:8]}{ext}"
    path = dir_path / safe_name
    path.write_bytes(content)

    theme.icon = f"logo:{safe_name}"
    db.add(AuditLog(user_id=require_admin(require_auth(request)).id, action="theme_logo_upload",
                     detail=f'{{"theme_id":{theme_id},"filename":"{safe_name}"}}',
                     ip_address=request.client.host if request.client else None))
    db.commit()
    from ..backup import schedule_backup
    schedule_backup()
    return {"filename": safe_name, "url": f"/logos/{safe_name}"}


@router.delete("/themes/{theme_id}/logo")
async def delete_logo(theme_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(require_auth(request))
    theme = db.query(Theme).filter(Theme.id == theme_id).first()
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")

    old_icon = theme.icon
    if old_icon and old_icon.startswith("logo:"):
        fname = old_icon[6:]
        fpath = _logo_dir() / fname
        if fpath.exists():
            fpath.unlink()
    theme.icon = ""
    db.add(AuditLog(user_id=require_admin(require_auth(request)).id, action="theme_logo_delete",
                     detail=f'{{"theme_id":{theme_id}}}',
                     ip_address=request.client.host if request.client else None))
    db.commit()
    from ..backup import schedule_backup
    schedule_backup()
    return {"ok": True}
