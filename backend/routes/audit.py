from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import AuditLog
from ..auth import require_auth


router = APIRouter(prefix="/api", tags=["audit"])


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
