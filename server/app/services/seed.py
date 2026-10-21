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

        # 演示态势点：始终刷新 UA00x，保证「最近 N 小时」时间窗可查可连航迹
        _seed_situation_aircraft_points(db)
        # 演示检测任务与 UA001 近时足迹重叠，便于「时空关联态势点」
        _seed_demo_detection_task(db)

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


def _seed_situation_aircraft_points(db):
    """Write dense, recent tracks for demo aircraft (safe to re-run)."""
    demo_ids = ["UA001", "UA002", "UA003", "UA004"]
    db.query(SitAircraftPoint).filter(SitAircraftPoint.aircraft_id.in_(demo_ids)).delete(
        synchronize_session=False
    )

    # 与前端 el-date-picker 本地时间一致，避免 utcnow + ISO Z 造成查空
    now = datetime.now().replace(second=0, microsecond=0)
    # 每机 24 点，间隔 5 分钟，覆盖最近约 2 小时，便于按时间查点/连航迹
    steps = 24
    step_minutes = 5
    routes = [
        # aid, lon0, lat0, dlon, dlat, alt
        ("UA001", 116.20, 39.80, 0.012, 0.006, 7000),
        ("UA002", 116.35, 39.88, 0.010, -0.004, 7300),
        ("UA003", 116.50, 39.96, -0.008, 0.005, 7600),
        ("UA004", 116.28, 39.92, 0.006, 0.008, 6900),
    ]
    for aid, lon0, lat0, dlon, dlat, alt in routes:
        for j in range(steps):
            # j=0 最旧，j=steps-1 最新（贴近 now）
            age = (steps - 1 - j) * step_minutes
            db.add(
                SitAircraftPoint(
                    aircraft_id=aid,
                    lon=lon0 + j * dlon,
                    lat=lat0 + j * dlat,
                    alt=alt + (j % 5) * 20,
                    observed_at=now - timedelta(minutes=age),
                )
            )


DEMO_TASK_ID = "task-demo-1"


def _seed_demo_detection_task(db):
    """Rewrite the demo detection task so it stays inside the current situation window."""
    image_ids = [
        row[0]
        for row in db.query(SitTaskImage.id).filter(SitTaskImage.task_id == DEMO_TASK_ID).all()
    ]
    if image_ids:
        db.query(SitImageDetectionResult).filter(
            SitImageDetectionResult.image_id.in_(image_ids)
        ).delete(synchronize_session=False)
    db.query(SitTaskImage).filter(SitTaskImage.task_id == DEMO_TASK_ID).delete(synchronize_session=False)
    db.query(SitTrack).filter(SitTrack.task_id == DEMO_TASK_ID).delete(synchronize_session=False)
    existing = db.get(SitTaskInfo, DEMO_TASK_ID)
    if existing is not None:
        db.delete(existing)
    db.flush()

    now = datetime.now().replace(second=0, microsecond=0)
    # 8 frames, 5 min apart, ending now — overlaps the newest UA001 samples
    start = now - timedelta(minutes=35)
    db.add(
        SitTaskInfo(
            id=DEMO_TASK_ID,
            name="演示检测任务-1",
            status="running",
            start_time=start,
            end_time=now,
        )
    )
    db.flush()

    tracks: dict[str, list] = {"DET-A1": [], "DET-B2": []}
    for i, step in enumerate(range(16, 24)):
        observed = now - timedelta(minutes=(23 - step) * 5)
        base_lon = 116.20 + step * 0.012
        base_lat = 39.80 + step * 0.006
        image_id = f"img-demo-{i + 1:02d}"
        db.add(
            SitTaskImage(
                id=image_id,
                task_id=DEMO_TASK_ID,
                received_at=observed,
                image_url=f"https://picsum.photos/seed/platform2-{i}/640/360",
            )
        )
        db.flush()
        samples = (
            ("DET-A1", base_lon + 0.004, base_lat + 0.003, 8200, 0.93),
            ("DET-B2", base_lon - 0.006, base_lat + 0.008, 7900, 0.88),
        )
        for aircraft_id, lon, lat, alt, confidence in samples:
            db.add(
                SitImageDetectionResult(
                    image_id=image_id,
                    aircraft_id=aircraft_id,
                    lon=lon,
                    lat=lat,
                    alt=alt,
                    confidence=confidence,
                )
            )
            tracks[aircraft_id].append(
                {
                    "time_ms": int(observed.timestamp() * 1000),
                    "lon": lon,
                    "lat": lat,
                    "alt": alt,
                    "observed_at": observed.isoformat(),
                }
            )

    for aircraft_id, points in tracks.items():
        db.add(
            SitTrack(
                id=f"track-demo-{aircraft_id}",
                task_id=DEMO_TASK_ID,
                aircraft_id=aircraft_id,
                points_json=json.dumps(points),
            )
        )
