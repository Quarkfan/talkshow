import secrets
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from ..database import get_db
from ..models import ShareLink, AuditLog, Theme
from ..auth import require_auth, require_admin


class ShareCreateRequest(BaseModel):
    theme_id: int
    password: str | None = None
    expires_days: int | None = None


router = APIRouter(prefix="/api", tags=["shares"])


@router.post("/shares")
async def create_share(
    body: ShareCreateRequest, request: Request, db: Session = Depends(get_db)
):
    user = require_admin(require_auth(request))
    ip = request.client.host if request.client else None
    theme = db.query(Theme).filter(Theme.id == body.theme_id).first()
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    token = secrets.token_urlsafe(32)
    expires_at = None
    if body.expires_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_days)
    link = ShareLink(
        theme_id=body.theme_id, token=token,
        password=body.password,
        expires_at=expires_at, created_by=user.id
    )
    db.add(link)
    db.add(AuditLog(
        user_id=user.id, action="share_create",
        detail=f'{{"theme_id":{body.theme_id},"token":"{token[:8]}..."}}',
        ip_address=ip
    ))
    db.commit()
    db.refresh(link)
    from ..backup import schedule_backup
    schedule_backup()
    return {
        "id": link.id, "token": link.token,
        "url": f"/s/{link.token}",
        "expires_at": link.expires_at.isoformat() if link.expires_at else None
    }


@router.get("/shares")
async def list_shares(request: Request, db: Session = Depends(get_db)):
    require_auth(request)
    links = db.query(ShareLink).order_by(ShareLink.created_at.desc()).all()
    result = []
    for l in links:
        theme = db.query(Theme).filter(Theme.id == l.theme_id).first()
        result.append({
            "id": l.id, "theme_id": l.theme_id,
            "theme_title": theme.title if theme else "Unknown",
            "token": l.token[:12] + "...",
            "token_full": l.token,
            "active": l.active,
            "has_password": bool(l.password),
            "password": l.password or None,
            "allow_content": l.allow_content,
            "expires_at": l.expires_at.isoformat() if l.expires_at else None,
            "created_at": l.created_at.isoformat()
        })
    return result


@router.delete("/shares/{share_id}")
async def revoke_share(share_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_auth(request)
    ip = request.client.host if request.client else None
    link = db.query(ShareLink).filter(ShareLink.id == share_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Share link not found")
    link.active = False
    db.add(AuditLog(
        user_id=user.id, action="share_revoke",
        detail=f'{{"share_id":{share_id}}}',
        ip_address=ip
    ))
    db.commit()
    from ..backup import schedule_backup
    schedule_backup()
    return {"ok": True}


@router.delete("/shares/{share_id}/delete")
async def delete_share(share_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_admin(require_auth(request))
    ip = request.client.host if request.client else None
    link = db.query(ShareLink).filter(ShareLink.id == share_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Share link not found")
    theme = db.query(Theme).filter(Theme.id == link.theme_id).first()
    db.add(AuditLog(
        user_id=user.id, action="share_delete",
        detail=f'{{"share_id":{share_id},"theme":"{theme.title if theme else "Unknown"}","token":"{link.token[:8]}..."}}',
        ip_address=ip
    ))
    db.delete(link)
    db.commit()
    from ..backup import schedule_backup
    schedule_backup()
    return {"ok": True}


@router.patch("/shares/{share_id}/content")
async def toggle_share_content(share_id: int, request: Request, db: Session = Depends(get_db)):
    """Toggle whether this share link allows access to third-layer content files."""
    user = require_admin(require_auth(request))
    link = db.query(ShareLink).filter(ShareLink.id == share_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Share link not found")
    link.allow_content = not link.allow_content
    db.add(AuditLog(
        user_id=user.id, action="share_toggle_content",
        detail=f'{{"share_id":{share_id},"allow_content":{link.allow_content}}}',
        ip_address=request.client.host if request.client else None
    ))
    db.commit()
    from ..backup import schedule_backup
    schedule_backup()
    return {"id": link.id, "allow_content": link.allow_content}


@router.post("/shares/{token}/validate")
async def validate_share(token: str, body: dict, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None
    link = db.query(ShareLink).filter(ShareLink.token == token).first()
    if not link or not link.active:
        db.add(AuditLog(action="share_validate", detail=f'{{"token":"{token[:8]}...","result":"not_found"}}', ip_address=ip))
        db.commit()
        raise HTTPException(status_code=404, detail="Invalid or revoked link")
    expires_at = link.expires_at
    if expires_at and expires_at.tzinfo is None:
        from datetime import timezone as _tz
        expires_at = expires_at.replace(tzinfo=_tz.utc)
    if expires_at and expires_at < datetime.now(timezone.utc):
        link.active = False
        db.add(AuditLog(action="share_validate", detail=f'{{"token":"{token[:8]}...","result":"expired"}}', ip_address=ip))
        db.commit()
        raise HTTPException(status_code=410, detail="Share link expired")
    if link.password and body.get("password") != link.password:
        db.add(AuditLog(action="share_validate", detail=f'{{"token":"{token[:8]}...","result":"wrong_password"}}', ip_address=ip))
        db.commit()
        raise HTTPException(status_code=403, detail="Invalid password")
    theme = db.query(Theme).filter(Theme.id == link.theme_id).first()
    db.add(AuditLog(
        action="share_validate",
        detail=f'{{"token":"{token[:8]}...","theme_id":{link.theme_id},"result":"ok"}}',
        ip_address=ip
    ))
    db.commit()
    return {"theme_file": theme.theme_file, "title": theme.title}
