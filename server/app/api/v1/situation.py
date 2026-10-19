from datetime import datetime
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import SitAircraftPoint, SitTaskImage, SitTaskInfo, SitTrack, User
from app.services.situation_query import build_points_response, build_tracks_response

router = APIRouter(prefix="/situation", tags=["situation"])


class QueryBody(BaseModel):
    mode: str = "realtime"
    aircraft_id: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None


class TimeRangeBody(BaseModel):
    aircraft_id: str | None = Field(default=None, description="可选飞机编号")
    start_time: datetime = Field(description="查询开始时间（含）")
    end_time: datetime = Field(description="查询结束时间（含）")


@router.get("/aircraft/realtime", operation_id="get_realtime_aircraft_points")
def realtime_points(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """获取每架飞机最新实时态势点位。"""
    rows = db.query(SitAircraftPoint).order_by(SitAircraftPoint.observed_at.desc()).limit(50).all()
    latest = {}
    for row in rows:
        if row.aircraft_id not in latest:
            latest[row.aircraft_id] = row
    points = [
        {
            "aircraft_id": r.aircraft_id,
            "lon": r.lon,
            "lat": r.lat,
            "alt": r.alt,
            "observed_at": r.observed_at.isoformat(),
        }
        for r in latest.values()
    ]
    return {"points": points, "count": len(points)}


@router.post("/aircraft/query", operation_id="query_aircraft_points")
def query_points(body: QueryBody, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """按时间范围与可选机号查询态势点位，用于地球标绘。"""
    if (body.start_time is None) ^ (body.end_time is None):
        raise HTTPException(status_code=400, detail="start_time 与 end_time 需同时提供")
    return build_points_response(
        db,
        aircraft_id=body.aircraft_id,
        start_time=body.start_time,
        end_time=body.end_time,
        require_time_range=False,
    )


@router.post("/aircraft/tracks", operation_id="query_aircraft_tracks")
def query_tracks(body: TimeRangeBody, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """按时间范围将态势点位按时序合成为多机航迹，用于地球折线标绘。"""
    return build_tracks_response(
        db,
        aircraft_id=body.aircraft_id,
        start_time=body.start_time,
        end_time=body.end_time,
        require_time_range=True,
    )


@router.get("/task/list", operation_id="list_detection_tasks")
def task_list(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """列出图像检测任务。"""
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


@router.get("/task/{task_id}/timeline", operation_id="get_task_timeline")
def task_timeline(task_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """获取检测任务时间轴帧。"""
    images = (
        db.query(SitTaskImage)
        .filter(SitTaskImage.task_id == task_id)
        .order_by(SitTaskImage.received_at.asc())
        .all()
    )
    buckets: dict[int, list] = {}
    for img in images:
        key = int(img.received_at.timestamp())
        buckets.setdefault(key, []).append(img)

    frames = []
    for index, key in enumerate(sorted(buckets.keys())):
        group = buckets[key]
        first = group[0]
        frames.append(
            {
                "index": index,
                "timeMs": int(first.received_at.timestamp() * 1000),
                "reconTime": first.received_at.isoformat(),
                "imageCount": len(group),
                "imageUrl": first.image_url,
                "imageIds": [g.id for g in group],
            }
        )
    return {"frames": frames}


@router.get("/task/{task_id}/track", operation_id="get_task_track")
def task_track(task_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """获取检测任务合批航迹（非态势观测航迹）。"""
    rows = db.query(SitTrack).filter(SitTrack.task_id == task_id).all()
    if not rows:
        return {"task_id": task_id, "aircraft_id": None, "points": []}
    track = rows[0]
    return {
        "task_id": task_id,
        "aircraft_id": track.aircraft_id,
        "points": json.loads(track.points_json),
    }
