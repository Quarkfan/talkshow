from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from ..database import get_db, SessionLocal
from ..auth import authenticate_user
from ..models import User, AuditLog


class LoginRequest(BaseModel):
    username: str
    password: str


router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/login")
async def login(request: Request, body: LoginRequest, db=Depends(get_db)):
    user = authenticate_user(db, body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    request.session["user_id"] = user.id
    db.add(AuditLog(
        user_id=user.id, action="login",
        ip_address=request.client.host if request.client else None
    ))
    db.commit()
    return {"id": user.id, "username": user.username, "role": user.role}


@router.post("/logout")
async def logout(request: Request, db=Depends(get_db)):
    user_id = request.session.get("user_id")
    if user_id:
        db.add(AuditLog(user_id=user_id, action="logout"))
        db.commit()
    request.session.clear()
    return {"ok": True}


@router.get("/me")
async def me(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    db.close()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return {"id": user.id, "username": user.username, "role": user.role}
