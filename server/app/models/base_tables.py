from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="operator")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DifyAgentRegistry(Base):
    __tablename__ = "dify_agent_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    app_id: Mapped[str] = mapped_column(String(128), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    app_type: Mapped[str] = mapped_column(String(32), default="workflow")
    intent_desc: Mapped[str] = mapped_column(String(255), default="")
    keywords: Mapped[str] = mapped_column(String(255), default="")
    api_key: Mapped[str] = mapped_column(String(255), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AiChatSession(Base):
    __tablename__ = "ai_chat_session"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AiChatMessage(Base):
    __tablename__ = "ai_chat_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("ai_chat_session.id"), index=True)
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AiToolCall(Base):
    __tablename__ = "ai_tool_call"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    tool_name: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
