from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.db import get_db
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    token = create_access_token(user.username, user.role)
    return {"access_token": token, "token_type": "bearer", "role": user.role}
