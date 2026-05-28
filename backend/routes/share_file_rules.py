from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import ShareFileRule, ShareLink, Theme, ContentRule, AuditLog
from ..utils import resolve_file_theme, scan_files
from ..auth import require_auth, require_admin


class ShareFileRuleUpdate(BaseModel):
    public: bool


router = APIRouter(prefix="/api", tags=["share-file-rules"])


@router.get("/shares/{share_id}/files")
async def list_share_files(share_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(require_auth(request))

    link = db.query(ShareLink).filter(ShareLink.id == share_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Share link not found")

    theme = db.query(Theme).filter(Theme.id == link.theme_id).first()
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")

    content_dir = request.app.state.content_dir
    all_files = scan_files(str(content_dir))
    themes = db.query(Theme).all()

    db_content_rules = {r.path: r for r in db.query(ContentRule).all()}
    db_share_rules = {r.path: r for r in db.query(ShareFileRule).filter(
        ShareFileRule.share_id == share_id
    ).all()}

    result = []
    for f in all_files:
        parent = resolve_file_theme(f, themes)
        if parent and parent.id != link.theme_id:
            # File belongs to a different theme, skip
            continue

        share_rule = db_share_rules.get(f)
        content_rule = db_content_rules.get(f)

        if share_rule:
            effective_public = share_rule.public
            source = "share_rule"
        elif content_rule:
            effective_public = content_rule.public
            source = "global_rule"
        elif parent and parent.id == link.theme_id:
            effective_public = theme.accessible
            source = "theme_default"
        else:
            # Unmatched file (e.g., presentations/xxx) — default to share's theme accessible
            effective_public = theme.accessible
            source = "theme_default"

        result.append({
            "path": f,
            "has_share_rule": share_rule is not None,
            "has_global_rule": content_rule is not None,
            "share_rule_id": share_rule.id if share_rule else None,
            "public": effective_public,
            "source": source,
            "theme_title": theme.title if not parent or parent.id != link.theme_id else parent.title,
            "theme_accessible": theme.accessible,
        })
    return result


@router.patch("/shares/{share_id}/files/{path:path}")
async def update_share_file_rule(
    share_id: int, path: str, body: ShareFileRuleUpdate,
    request: Request, db: Session = Depends(get_db),
):
    require_admin(require_auth(request))

    link = db.query(ShareLink).filter(ShareLink.id == share_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Share link not found")

    from urllib.parse import unquote
    clean_path = unquote(path)

    rule = db.query(ShareFileRule).filter(
        ShareFileRule.share_id == share_id,
        ShareFileRule.path == clean_path,
    ).first()

    if rule:
        rule.public = body.public
    else:
        rule = ShareFileRule(share_id=share_id, path=clean_path, public=body.public)
        db.add(rule)

    db.add(AuditLog(
        action="share_file_rule_update",
        detail=f'{{"share_id":{share_id},"path":"{clean_path}","public":{body.public}}}',
        ip_address=request.client.host if request.client else None,
    ))
    db.commit()
    db.refresh(rule)
    from ..backup import schedule_backup
    schedule_backup()
    return {"id": rule.id, "path": rule.path, "public": rule.public}
