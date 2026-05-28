import os
from pathlib import Path
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import ContentRule, AuditLog, Theme
from ..utils import resolve_file_theme, scan_files
from ..auth import require_auth, require_admin


router = APIRouter(prefix="/api", tags=["content-rules"])


class RuleToggle(BaseModel):
    public: bool


class RuleCreate(BaseModel):
    path: str
    public: bool


class BulkToggle(BaseModel):
    public: bool


@router.get("/content-rules")
async def list_content_rules(request: Request, db: Session = Depends(get_db)):
    """List all files with their public status and inherited theme info."""
    require_auth(request)
    content_dir = request.app.state.content_dir
    files = scan_files(str(content_dir))
    db_rules = {r.path: r for r in db.query(ContentRule).all()}
    themes = db.query(Theme).all()
    theme_map = {t.id: t for t in themes}

    result = []
    for f in files:
        rule = db_rules.get(f)
        parent_theme = resolve_file_theme(f, themes)
        theme_visible = parent_theme.visible if parent_theme else False
        if rule:
            public = rule.public
            source = "rule"
        else:
            public = theme_visible
            source = "inherited"
        result.append({
            "path": f,
            "id": rule.id if rule else None,
            "public": public,
            "source": source,
            "has_rule": rule is not None,
            "theme_id": parent_theme.id if parent_theme else None,
            "theme_title": parent_theme.title if parent_theme else None,
            "theme_visible": theme_visible,
        })
    return result


@router.post("/content-rules")
async def create_content_rule(
    body: RuleCreate, request: Request, db: Session = Depends(get_db)
):
    """Create a rule for a file that doesn't have one yet."""
    user = require_admin(require_auth(request))
    existing = db.query(ContentRule).filter(ContentRule.path == body.path).first()
    if existing:
        raise HTTPException(status_code=409, detail="Rule already exists")
    themes = db.query(Theme).all()
    parent = resolve_file_theme(body.path, themes)
    rule = ContentRule(path=body.path, public=body.public, theme_id=parent.id if parent else None)
    db.add(rule)
    db.add(AuditLog(
        user_id=user.id, action="content_rule_create",
        detail=f'{{"path":"{body.path}","public":{body.public},"theme_id":{parent.id if parent else 0}}}'
    ))
    db.commit()
    db.refresh(rule)
    from ..backup import schedule_backup
    schedule_backup()
    return {"id": rule.id, "path": rule.path, "public": rule.public}


@router.patch("/content-rules/{rule_id}")
async def toggle_content_rule(
    rule_id: int, body: RuleToggle, request: Request, db: Session = Depends(get_db)
):
    user = require_admin(require_auth(request))
    rule = db.query(ContentRule).filter(ContentRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.public = body.public
    db.add(AuditLog(
        user_id=user.id, action="content_rule_toggle",
        detail=f'{{"path":"{rule.path}","public":{body.public}}}'
    ))
    db.commit()
    from ..backup import schedule_backup
    schedule_backup()
    return {"id": rule.id, "path": rule.path, "public": rule.public}


@router.post("/content-rules/bulk")
async def bulk_toggle(body: BulkToggle, request: Request, db: Session = Depends(get_db)):
    """Toggle all files at once. Creates rules for files that don't have them."""
    user = require_admin(require_auth(request))
    content_dir = request.app.state.content_dir
    files = scan_files(str(content_dir))
    existing = {r.path: r for r in db.query(ContentRule).all()}
    themes = db.query(Theme).all()

    count = 0
    for f in files:
        rule = existing.get(f)
        if rule:
            if rule.public != body.public:
                rule.public = body.public
                count += 1
        else:
            parent = resolve_file_theme(f, themes)
            rule = ContentRule(path=f, public=body.public, theme_id=parent.id if parent else None)
            db.add(rule)
            count += 1

    db.add(AuditLog(
        user_id=user.id, action="content_rule_bulk",
        detail=f'{{"public":{body.public},"count":{count}}}'
    ))
    db.commit()
    from ..backup import schedule_backup
    schedule_backup()
    return {"ok": True, "changed": count}
