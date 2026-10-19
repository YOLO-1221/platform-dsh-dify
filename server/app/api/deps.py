from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import ALGORITHM
from app.db import get_db
from app.models import User

security = HTTPBearer(auto_error=False)


def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if cred is None:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = jwt.decode(cred.credentials, settings.secret_key, algorithms=[ALGORITHM])
        username = payload.get("sub")
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="无效令牌") from exc
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
