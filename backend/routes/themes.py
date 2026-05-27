from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Theme, AuditLog
from ..auth import require_auth, require_admin
from ..init_db import scan_content_dir


router = APIRouter(prefix="/api", tags=["themes"])


@router.get("/themes/public")
async def list_public_themes(db: Session = Depends(get_db)):
    themes = db.query(Theme).filter(Theme.visible == True).all()
    return [{
        "id": t.id, "slug": t.slug, "title": t.title,
        "description": t.description, "icon": t.icon,
        "tags": t.tags.split(",") if t.tags else [],
        "presentation_count": t.presentation_count,
        "theme_file": t.theme_file
    } for t in themes]


@router.get("/themes")
async def list_all_themes(request: Request, db: Session = Depends(get_db)):
    require_auth(request)
    themes = db.query(Theme).all()
    return [{
        "id": t.id, "slug": t.slug, "title": t.title,
        "visible": t.visible, "theme_file": t.theme_file,
        "icon": t.icon, "tags": t.tags,
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
        user_id=user.id, action="theme_toggle",
        detail=f'{{"theme_id":{theme_id},"visible":{theme.visible}}}'
    ))
    db.commit()
    return {"id": theme.id, "visible": theme.visible}


@router.post("/themes/rescan")
async def rescan_themes(request: Request, db: Session = Depends(get_db)):
    user = require_admin(require_auth(request))
    scan_content_dir(request.app.state.content_dir)
    db.add(AuditLog(user_id=user.id, action="rescan"))
    db.commit()
    return {"ok": True}
