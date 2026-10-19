import json
from datetime import datetime, timedelta

from sqlalchemy import text

from app.core.security import hash_password
from app.db import SessionLocal, engine
from app.models import (
    DifyAgentRegistry,
    SitAircraftPoint,
    SitImageDetectionResult,
    SitTaskImage,
    SitTaskInfo,
    SitTrack,
    User,
)


def ensure_registry_columns():
    """create_all does not add columns to an existing PostgreSQL table."""
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE dify_agent_registry ADD COLUMN IF NOT EXISTS keywords VARCHAR(255) NOT NULL DEFAULT ''"
        ))
        conn.execute(text(
            "ALTER TABLE dify_agent_registry ADD COLUMN IF NOT EXISTS api_key VARCHAR(255) NOT NULL DEFAULT ''"
        ))


def ensure_seed_data():
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == "operator").first():
            db.add(User(username="operator", password_hash=hash_password("operator"), role="operator"))
            db.add(User(username="admin", password_hash=hash_password("admin"), role="admin"))

        if not db.query(DifyAgentRegistry).first():
            db.add(
                DifyAgentRegistry(
                    app_id="situation-query",
                    name="态势查询工作流",
                    app_type="workflow",
                    intent_desc="飞机态势查询",
                    keywords="态势,飞机,点位,空域",
                    enabled=True,
                )
            )
            db.add(
                DifyAgentRegistry(
                    app_id="task-list",
                    name="任务列表查询工作流",
                    app_type="workflow",
                    intent_desc="检测任务列表",
                    keywords="任务,检测,航迹,时间轴",
                    enabled=True,
                )
            )

        if not db.query(SitAircraftPoint).first():
            now = datetime.utcnow()
            aircraft = ["UA001", "UA002", "UA003"]
            for i, aid in enumerate(aircraft):
                for j in range(8):
                    db.add(
                        SitAircraftPoint(
                            aircraft_id=aid,
                            lon=116.2 + i * 0.15 + j * 0.01,
                            lat=39.8 + i * 0.08 + j * 0.005,
                            alt=7000 + i * 300,
                            observed_at=now - timedelta(minutes=20 - j * 2),
                        )
                    )

        if not db.query(SitTaskInfo).first():
            start = datetime.utcnow().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
            end = start + timedelta(minutes=40)
            task_id = "task-demo-1"
            db.add(
                SitTaskInfo(
                    id=task_id,
                    name="演示检测任务-1",
                    status="running",
                    start_time=start,
                    end_time=end,
                )
            )
            db.flush()

            track_points = []
            for i in range(12):
                t = start + timedelta(minutes=i * 3)
                image_id = f"img-{i+1:02d}"
                lon = 116.35 + i * 0.02
                lat = 39.85 + i * 0.01
                db.add(
                    SitTaskImage(
                        id=image_id,
                        task_id=task_id,
                        received_at=t,
                        image_url=f"https://picsum.photos/seed/platform2-{i}/640/360",
                    )
                )
                db.flush()
                db.add(
                    SitImageDetectionResult(
                        image_id=image_id,
                        aircraft_id="DET-A1",
                        lon=lon,
                        lat=lat,
                        alt=8200,
                        confidence=0.92,
                    )
                )
                track_points.append(
                    {
                        "time_ms": int(t.timestamp() * 1000),
                        "lon": lon,
                        "lat": lat,
                        "alt": 8200,
                    }
                )

            db.add(
                SitTrack(
                    id="track-demo-1",
                    task_id=task_id,
                    aircraft_id="DET-A1",
                    points_json=json.dumps(track_points),
                )
            )

        keyword_defaults = {
            "situation-query": "态势,飞机,点位,空域",
            "task-list": "任务,检测,航迹,时间轴",
        }
        for app_id, words in keyword_defaults.items():
            row = db.query(DifyAgentRegistry).filter(DifyAgentRegistry.app_id == app_id).first()
            if row is not None and not (row.keywords or "").strip():
                row.keywords = words

        db.commit()
    finally:
        db.close()
