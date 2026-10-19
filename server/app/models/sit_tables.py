from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SitAircraftPoint(Base):
    __tablename__ = "sit_aircraft_point"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    aircraft_id: Mapped[str] = mapped_column(String(64), index=True)
    lon: Mapped[float] = mapped_column(Float)
    lat: Mapped[float] = mapped_column(Float)
    alt: Mapped[float] = mapped_column(Float, default=8000)
    observed_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class SitTaskInfo(Base):
    __tablename__ = "sit_task_info"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="running")
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)


class SitTaskImage(Base):
    __tablename__ = "sit_task_image"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("sit_task_info.id"), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    image_url: Mapped[str] = mapped_column(String(512))


class SitImageDetectionResult(Base):
    __tablename__ = "sit_image_detection_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    image_id: Mapped[str] = mapped_column(ForeignKey("sit_task_image.id"), index=True)
    aircraft_id: Mapped[str] = mapped_column(String(64), index=True)
    lon: Mapped[float] = mapped_column(Float)
    lat: Mapped[float] = mapped_column(Float)
    alt: Mapped[float] = mapped_column(Float, default=8000)
    confidence: Mapped[float] = mapped_column(Float, default=0.9)


class SitTrack(Base):
    __tablename__ = "sit_track"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("sit_task_info.id"), index=True)
    aircraft_id: Mapped[str] = mapped_column(String(64), index=True)
    points_json: Mapped[str] = mapped_column(Text)
