from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import SitAircraftPoint, SitTaskImage, SitTaskInfo, SitTrack, User
import json

router = APIRouter(prefix="/situation", tags=["situation"])


class QueryBody(BaseModel):
    mode: str = "realtime"
    aircraft_id: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None


@router.get("/aircraft/realtime")
def realtime_points(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.query(SitAircraftPoint).order_by(SitAircraftPoint.observed_at.desc()).limit(50).all()
    # keep latest per aircraft
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
    return {"points": points}


@router.post("/aircraft/query")
def query_points(body: QueryBody, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    q = db.query(SitAircraftPoint)
    if body.aircraft_id:
        q = q.filter(SitAircraftPoint.aircraft_id == body.aircraft_id)
    if body.start_time:
        q = q.filter(SitAircraftPoint.observed_at >= body.start_time)
    if body.end_time:
        q = q.filter(SitAircraftPoint.observed_at <= body.end_time)
    rows = q.order_by(SitAircraftPoint.observed_at.asc()).limit(500).all()
    return {
        "points": [
            {
                "aircraft_id": r.aircraft_id,
                "lon": r.lon,
                "lat": r.lat,
                "alt": r.alt,
                "observed_at": r.observed_at.isoformat(),
            }
            for r in rows
        ]
    }


@router.get("/task/list")
def task_list(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
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


@router.get("/task/{task_id}/timeline")
def task_timeline(task_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    images = (
        db.query(SitTaskImage)
        .filter(SitTaskImage.task_id == task_id)
        .order_by(SitTaskImage.received_at.asc())
        .all()
    )
    # group same second into one frame
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


@router.get("/task/{task_id}/track")
def task_track(task_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.query(SitTrack).filter(SitTrack.task_id == task_id).all()
    if not rows:
        return {"task_id": task_id, "aircraft_id": None, "points": []}
    # return first aircraft track for skeleton
    track = rows[0]
    return {
        "task_id": task_id,
        "aircraft_id": track.aircraft_id,
        "points": json.loads(track.points_json),
    }
