"""Shared situation point / track query helpers for public and internal APIs."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import SitAircraftPoint

POINT_LIMIT = 2000


def query_aircraft_rows(
    db: Session,
    *,
    aircraft_id: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    require_time_range: bool = False,
    limit: int = POINT_LIMIT,
) -> tuple[list[SitAircraftPoint], bool]:
    if require_time_range and (start_time is None or end_time is None):
        raise HTTPException(status_code=400, detail="start_time 与 end_time 必填")
    if start_time is not None and end_time is not None and start_time > end_time:
        raise HTTPException(status_code=400, detail="start_time 不能晚于 end_time")

    q = db.query(SitAircraftPoint)
    if aircraft_id:
        q = q.filter(SitAircraftPoint.aircraft_id == aircraft_id)
    if start_time is not None:
        q = q.filter(SitAircraftPoint.observed_at >= start_time)
    if end_time is not None:
        q = q.filter(SitAircraftPoint.observed_at <= end_time)
    rows = q.order_by(SitAircraftPoint.observed_at.asc()).limit(limit + 1).all()
    truncated = len(rows) > limit
    if truncated:
        rows = rows[:limit]
    return rows, truncated


def serialize_point(row: SitAircraftPoint) -> dict:
    return {
        "aircraft_id": row.aircraft_id,
        "lon": row.lon,
        "lat": row.lat,
        "alt": row.alt,
        "observed_at": row.observed_at.isoformat(),
    }


def build_points_response(
    db: Session,
    *,
    aircraft_id: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    require_time_range: bool = False,
) -> dict:
    rows, truncated = query_aircraft_rows(
        db,
        aircraft_id=aircraft_id,
        start_time=start_time,
        end_time=end_time,
        require_time_range=require_time_range,
    )
    points = [serialize_point(r) for r in rows]
    return {
        "points": points,
        "count": len(points),
        "truncated": truncated,
        "start_time": start_time.isoformat() if start_time else None,
        "end_time": end_time.isoformat() if end_time else None,
        "aircraft_id": aircraft_id,
    }


def build_tracks_response(
    db: Session,
    *,
    aircraft_id: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    require_time_range: bool = True,
) -> dict:
    rows, truncated = query_aircraft_rows(
        db,
        aircraft_id=aircraft_id,
        start_time=start_time,
        end_time=end_time,
        require_time_range=require_time_range,
    )
    grouped: dict[str, list] = defaultdict(list)
    for row in rows:
        grouped[row.aircraft_id].append(
            {
                "lon": row.lon,
                "lat": row.lat,
                "alt": row.alt,
                "time_ms": int(row.observed_at.timestamp() * 1000),
                "observed_at": row.observed_at.isoformat(),
            }
        )
    tracks = [
        {"aircraft_id": aid, "points": pts}
        for aid, pts in grouped.items()
        if len(pts) >= 2
    ]
    tracks.sort(key=lambda t: t["aircraft_id"])
    return {
        "tracks": tracks,
        "count": len(tracks),
        "point_count": len(rows),
        "truncated": truncated,
        "start_time": start_time.isoformat() if start_time else None,
        "end_time": end_time.isoformat() if end_time else None,
        "aircraft_id": aircraft_id,
    }
