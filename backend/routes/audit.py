from datetime import datetime
from fastapi import APIRouter, Depends, Request, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import AuditLog
from ..auth import require_auth, require_admin


router = APIRouter(prefix="/api", tags=["audit"])


class AuditCleanup(BaseModel):
    before_date: str  # ISO date string


@router.get("/audit")
async def list_audit_logs(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, le=200),
):
    require_auth(request)
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [{
        "id": l.id, "user_id": l.user_id, "action": l.action,
        "detail": l.detail, "ip_address": l.ip_address,
        "created_at": l.created_at.isoformat()
    } for l in logs]


@router.post("/audit/cleanup")
async def cleanup_audit_logs(
    body: AuditCleanup, request: Request, db: Session = Depends(get_db)
):
    user = require_admin(require_auth(request))
    cutoff = datetime.fromisoformat(body.before_date)
    deleted = db.query(AuditLog).filter(AuditLog.created_at < cutoff).delete()
    db.add(AuditLog(
        user_id=user.id, action="audit_cleanup",
        detail=f'{{"before":"{body.before_date}","deleted":{deleted}}}',
        ip_address=request.client.host if request.client else None
    ))
    db.commit()
    return {"ok": True, "deleted": deleted}
