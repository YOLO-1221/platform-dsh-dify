"""Service-token endpoints used by Dify tools, local runners, and Harness bridge."""

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import DifyAgentRegistry, SitAircraftPoint, SitTaskInfo
from app.services.situation_query import build_points_response, build_tracks_response
from app.services.task_workflow import (
    associated_situation,
    detection_images,
    detection_points,
    detection_tracks,
    open_task,
)

router = APIRouter(prefix="/internal", tags=["internal"])


class TimeRangeBody(BaseModel):
    aircraft_id: str | None = Field(default=None, description="可选飞机编号")
    start_time: datetime = Field(description="查询开始时间（含）")
    end_time: datetime = Field(description="查询结束时间（含）")


def require_service(authorization: str | None = Header(default=None)) -> None:
    expected = f"Bearer {settings.service_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="invalid service token")


@router.get("/dify/apps", operation_id="internal_list_dify_apps")
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


@router.get("/situation/aircraft/realtime", operation_id="internal_get_realtime_aircraft_points")
def realtime(_: None = Depends(require_service), db: Session = Depends(get_db)):
    """服务令牌：每架飞机最新实时态势点位。"""
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
        ],
        "count": len(latest),
    }


@router.post("/situation/aircraft/query", operation_id="internal_query_aircraft_points")
def query_points(
    body: TimeRangeBody,
    _: None = Depends(require_service),
    db: Session = Depends(get_db),
):
    """服务令牌：按时间查态势点位（供 Dify Custom Tool / OpenAPI 导入）。"""
    return build_points_response(
        db,
        aircraft_id=body.aircraft_id,
        start_time=body.start_time,
        end_time=body.end_time,
        require_time_range=True,
    )


@router.post("/situation/aircraft/tracks", operation_id="internal_query_aircraft_tracks")
def query_tracks(
    body: TimeRangeBody,
    _: None = Depends(require_service),
    db: Session = Depends(get_db),
):
    """服务令牌：按时间查态势航迹（供 Dify Custom Tool / OpenAPI 导入）。"""
    return build_tracks_response(
        db,
        aircraft_id=body.aircraft_id,
        start_time=body.start_time,
        end_time=body.end_time,
        require_time_range=True,
    )


@router.get("/situation/task/list", operation_id="internal_list_detection_tasks")
def tasks(_: None = Depends(require_service), db: Session = Depends(get_db)):
    """服务令牌：检测任务列表。"""
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


@router.get("/situation/task/{task_id}", operation_id="internal_open_detection_task")
def task_open(task_id: str, _: None = Depends(require_service), db: Session = Depends(get_db)):
    """服务令牌：打开检测任务（元数据与图层数量）。"""
    return open_task(db, task_id)


@router.get("/situation/task/{task_id}/detections", operation_id="internal_get_task_detection_points")
def task_detections(task_id: str, _: None = Depends(require_service), db: Session = Depends(get_db)):
    """服务令牌：任务检测点。"""
    return detection_points(db, task_id)


@router.get("/situation/task/{task_id}/tracks", operation_id="internal_get_task_detection_tracks")
def task_detection_tracks(task_id: str, _: None = Depends(require_service), db: Session = Depends(get_db)):
    """服务令牌：任务检测航迹。"""
    return detection_tracks(db, task_id)


@router.get("/situation/task/{task_id}/images", operation_id="internal_get_task_detection_images")
def task_images(task_id: str, _: None = Depends(require_service), db: Session = Depends(get_db)):
    """服务令牌：任务检测图像。"""
    return detection_images(db, task_id)


@router.get(
    "/situation/task/{task_id}/associated-situation",
    operation_id="internal_get_task_associated_situation",
)
def task_associated(task_id: str, _: None = Depends(require_service), db: Session = Depends(get_db)):
    """服务令牌：与任务时空重叠的态势点。"""
    return associated_situation(db, task_id)
