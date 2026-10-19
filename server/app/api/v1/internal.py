"""Service-token endpoints used by the local Dify runner and Harness bridge."""

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import DifyAgentRegistry, SitAircraftPoint, SitTaskInfo

router = APIRouter(prefix="/internal", tags=["internal"])


def require_service(authorization: str | None = Header(default=None)) -> None:
    expected = f"Bearer {settings.service_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="invalid service token")


@router.get("/dify/apps")
def list_apps(_: None = Depends(require_service), db: Session = Depends(get_db)):
    rows = db.query(DifyAgentRegistry).all()
    return {
        "items": [
            {
                "app_id": r.app_id,
                "name": r.name,
                "app_type": r.app_type,
                "intent_desc": r.intent_desc,
                "keywords": r.keywords or "",
                "api_key": r.api_key or "",
                "enabled": r.enabled,
            }
            for r in rows
        ]
    }


@router.get("/situation/aircraft/realtime")
def realtime(_: None = Depends(require_service), db: Session = Depends(get_db)):
    rows = db.query(SitAircraftPoint).order_by(SitAircraftPoint.observed_at.desc()).limit(50).all()
    latest = {}
    for row in rows:
        latest.setdefault(row.aircraft_id, row)
    return {
        "points": [
            {
                "aircraft_id": r.aircraft_id,
                "lon": r.lon,
                "lat": r.lat,
                "alt": r.alt,
                "observed_at": r.observed_at.isoformat(),
            }
            for r in latest.values()
        ]
    }


@router.get("/situation/task/list")
def tasks(_: None = Depends(require_service), db: Session = Depends(get_db)):
    rows = db.query(SitTaskInfo).order_by(SitTaskInfo.start_time.desc()).all()
    return {
        "tasks": [
            {
                "id": t.id,
                "name": t.name,
                "status": t.status,
                "start_time": t.start_time.isoformat(),
                "end_time": t.end_time.isoformat(),
            }
            for t in rows
        ]
    }
