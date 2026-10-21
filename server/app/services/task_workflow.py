"""Task workflow: open a detection task, then load points, tracks, images, and linked situation."""

from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import SitAircraftPoint, SitImageDetectionResult, SitTaskImage, SitTaskInfo, SitTrack

# ~5 km at mid-latitudes; keeps association local to the detection footprint.
SPATIAL_PAD_DEG = 0.05


def require_task(db: Session, task_id: str) -> SitTaskInfo:
    task = db.get(SitTaskInfo, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


def serialize_task(task: SitTaskInfo) -> dict:
    return {
        "id": task.id,
        "name": task.name,
        "status": task.status,
        "start_time": task.start_time.isoformat(),
        "end_time": task.end_time.isoformat(),
    }


def open_task(db: Session, task_id: str) -> dict:
    """Return task metadata and layer counts without plotting data."""
    task = require_task(db, task_id)
    image_count = db.query(SitTaskImage).filter(SitTaskImage.task_id == task_id).count()
    detection_count = (
        db.query(SitImageDetectionResult)
        .join(SitTaskImage, SitImageDetectionResult.image_id == SitTaskImage.id)
        .filter(SitTaskImage.task_id == task_id)
        .count()
    )
    track_count = db.query(SitTrack).filter(SitTrack.task_id == task_id).count()
    return {
        "task": serialize_task(task),
        "image_count": image_count,
        "detection_count": detection_count,
        "track_count": track_count,
    }


def _detection_rows(db: Session, task_id: str) -> list[tuple[SitImageDetectionResult, SitTaskImage]]:
    return (
        db.query(SitImageDetectionResult, SitTaskImage)
        .join(SitTaskImage, SitImageDetectionResult.image_id == SitTaskImage.id)
        .filter(SitTaskImage.task_id == task_id)
        .order_by(SitTaskImage.received_at.asc(), SitImageDetectionResult.id.asc())
        .all()
    )


def detection_points(db: Session, task_id: str) -> dict:
    require_task(db, task_id)
    points = []
    for det, image in _detection_rows(db, task_id):
        points.append(
            {
                "id": det.id,
                "image_id": det.image_id,
                "aircraft_id": det.aircraft_id,
                "lon": det.lon,
                "lat": det.lat,
                "alt": det.alt,
                "confidence": det.confidence,
                "observed_at": image.received_at.isoformat(),
                "time_ms": int(image.received_at.timestamp() * 1000),
                "kind": "detection",
            }
        )
    return {"task_id": task_id, "points": points, "count": len(points)}


def detection_tracks(db: Session, task_id: str) -> dict:
    require_task(db, task_id)
    rows = (
        db.query(SitTrack)
        .filter(SitTrack.task_id == task_id)
        .order_by(SitTrack.aircraft_id.asc())
        .all()
    )
    tracks = []
    for row in rows:
        raw = json.loads(row.points_json or "[]")
        points = raw if isinstance(raw, list) else []
        tracks.append(
            {
                "id": row.id,
                "aircraft_id": row.aircraft_id,
                "points": points,
                "kind": "detection",
            }
        )
    return {"task_id": task_id, "tracks": tracks, "count": len(tracks)}


def _frames_from_images(images: list[SitTaskImage]) -> list[dict]:
    buckets: dict[int, list[SitTaskImage]] = {}
    for image in images:
        buckets.setdefault(int(image.received_at.timestamp()), []).append(image)
    frames = []
    for index, key in enumerate(sorted(buckets)):
        group = buckets[key]
        first = group[0]
        frames.append(
            {
                "index": index,
                "timeMs": int(first.received_at.timestamp() * 1000),
                "reconTime": first.received_at.isoformat(),
                "imageCount": len(group),
                "imageUrl": first.image_url,
                "imageIds": [item.id for item in group],
            }
        )
    return frames


def detection_images(db: Session, task_id: str) -> dict:
    require_task(db, task_id)
    images = (
        db.query(SitTaskImage)
        .filter(SitTaskImage.task_id == task_id)
        .order_by(SitTaskImage.received_at.asc())
        .all()
    )
    payload = [
        {
            "id": image.id,
            "task_id": image.task_id,
            "received_at": image.received_at.isoformat(),
            "image_url": image.image_url,
            "time_ms": int(image.received_at.timestamp() * 1000),
        }
        for image in images
    ]
    return {
        "task_id": task_id,
        "images": payload,
        "frames": _frames_from_images(images),
        "count": len(payload),
    }


def _spatial_window(rows: list[tuple[SitImageDetectionResult, SitTaskImage]]) -> dict | None:
    if not rows:
        return None
    lons = [det.lon for det, _ in rows]
    lats = [det.lat for det, _ in rows]
    return {
        "min_lon": min(lons) - SPATIAL_PAD_DEG,
        "max_lon": max(lons) + SPATIAL_PAD_DEG,
        "min_lat": min(lats) - SPATIAL_PAD_DEG,
        "max_lat": max(lats) + SPATIAL_PAD_DEG,
    }


def associated_situation(db: Session, task_id: str) -> dict:
    """Situation points inside the task time span and near its detection footprint."""
    task = require_task(db, task_id)
    dets = _detection_rows(db, task_id)
    window = _spatial_window(dets)
    q = db.query(SitAircraftPoint).filter(
        SitAircraftPoint.observed_at >= task.start_time,
        SitAircraftPoint.observed_at <= task.end_time,
    )
    if window is not None:
        q = q.filter(
            SitAircraftPoint.lon >= window["min_lon"],
            SitAircraftPoint.lon <= window["max_lon"],
            SitAircraftPoint.lat >= window["min_lat"],
            SitAircraftPoint.lat <= window["max_lat"],
        )
    rows = q.order_by(SitAircraftPoint.observed_at.asc()).all()
    points = [
        {
            "id": row.id,
            "aircraft_id": row.aircraft_id,
            "lon": row.lon,
            "lat": row.lat,
            "alt": row.alt,
            "observed_at": row.observed_at.isoformat(),
            "time_ms": int(row.observed_at.timestamp() * 1000),
            "kind": "situation",
        }
        for row in rows
    ]
    return {
        "task_id": task_id,
        "points": points,
        "count": len(points),
        "window": {
            "start_time": task.start_time.isoformat(),
            "end_time": task.end_time.isoformat(),
            **(window or {}),
            "spatial": window is not None,
        },
    }


def timeline_frames(db: Session, task_id: str) -> dict:
    images = (
        db.query(SitTaskImage)
        .filter(SitTaskImage.task_id == task_id)
        .order_by(SitTaskImage.received_at.asc())
        .all()
    )
    return {"frames": _frames_from_images(images)}
