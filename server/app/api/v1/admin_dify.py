from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db import get_db
from app.models import DifyAgentRegistry, User

router = APIRouter(prefix="/admin/dify", tags=["admin-dify"])


class DifyBody(BaseModel):
    app_id: str
    name: str
    app_type: str = "workflow"
    intent_desc: str = ""
    keywords: str = ""
    api_key: str = ""
    enabled: bool = True


class DifyUpdateBody(BaseModel):
    name: str | None = None
    app_type: str | None = None
    intent_desc: str | None = None
    keywords: str | None = None
    api_key: str | None = None
    enabled: bool | None = None


def _row_dict(r: DifyAgentRegistry) -> dict:
    return {
        "id": r.id,
        "app_id": r.app_id,
        "name": r.name,
        "app_type": r.app_type,
        "intent_desc": r.intent_desc,
        "keywords": r.keywords or "",
        "api_key": r.api_key or "",
        "enabled": r.enabled,
    }


@router.get("")
def list_apps(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    rows = db.query(DifyAgentRegistry).order_by(DifyAgentRegistry.id.asc()).all()
    return {"items": [_row_dict(r) for r in rows]}


@router.post("")
def create_app(body: DifyBody, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if db.query(DifyAgentRegistry).filter(DifyAgentRegistry.app_id == body.app_id).first():
        raise HTTPException(status_code=400, detail="app_id 已存在")
    row = DifyAgentRegistry(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_dict(row)


@router.put("/{app_id}")
def update_app(
    app_id: str,
    body: DifyUpdateBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    row = db.query(DifyAgentRegistry).filter(DifyAgentRegistry.app_id == app_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="应用不存在")
    data = body.model_dump(exclude_unset=True)
    if data.get("api_key") == "":
        data.pop("api_key", None)
    for key, value in data.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return _row_dict(row)


@router.delete("/{app_id}")
def delete_app(app_id: str, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    row = db.query(DifyAgentRegistry).filter(DifyAgentRegistry.app_id == app_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="应用不存在")
    db.delete(row)
    db.commit()
    return {"ok": True}
