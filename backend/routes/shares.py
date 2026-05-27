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
        detail=f'{{"theme_id":{body.theme_id},"token":"{token[:8]}..."}}'
    ))
    db.commit()
    db.refresh(link)
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
            "expires_at": l.expires_at.isoformat() if l.expires_at else None,
            "created_at": l.created_at.isoformat()
        })
    return result


@router.delete("/shares/{share_id}")
async def revoke_share(share_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_auth(request)
    link = db.query(ShareLink).filter(ShareLink.id == share_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Share link not found")
    link.active = False
    db.add(AuditLog(
        user_id=user.id, action="share_revoke",
        detail=f'{{"share_id":{share_id}}}'
    ))
    db.commit()
    return {"ok": True}


@router.post("/shares/{token}/validate")
async def validate_share(token: str, body: dict, db: Session = Depends(get_db)):
    link = db.query(ShareLink).filter(ShareLink.token == token).first()
    if not link or not link.active:
        raise HTTPException(status_code=404, detail="Invalid or revoked link")
    if link.expires_at and link.expires_at < datetime.now(timezone.utc):
        link.active = False
        db.commit()
        raise HTTPException(status_code=410, detail="Share link expired")
    if link.password and body.get("password") != link.password:
        raise HTTPException(status_code=403, detail="Invalid password")
    theme = db.query(Theme).filter(Theme.id == link.theme_id).first()
    db.add(AuditLog(
        action="share_access",
        detail=f'{{"token":"{token[:8]}...","theme_id":{link.theme_id}}}'
    ))
    db.commit()
    return {"theme_file": theme.theme_file, "title": theme.title}
