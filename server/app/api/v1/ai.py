import asyncio
import json
import uuid

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db import get_db
from app.models import AiChatMessage, AiChatSession, AiToolCall, SitAircraftPoint, SitTaskInfo, User

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat/session")
def create_session(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    sid = str(uuid.uuid4())
    db.add(AiChatSession(id=sid, user_id=user.id))
    db.commit()
    return {"id": sid}


@router.delete("/chat/session/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    db.query(AiChatMessage).filter(AiChatMessage.session_id == session_id).delete()
    db.query(AiChatSession).filter(AiChatSession.id == session_id).delete()
    db.commit()
    return {"ok": True}


@router.get("/tool-calls")
def list_tool_calls(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.query(AiToolCall).order_by(AiToolCall.created_at.desc()).limit(100).all()
    return {
        "items": [
            {
                "created_at": r.created_at.isoformat(),
                "session_id": r.session_id,
                "tool_name": r.tool_name,
                "summary": r.summary,
            }
            for r in rows
        ]
    }


async def _mock_sse(db: Session, session_id: str, query: str):
    yield _sse({"event_type": "thinking", "content": "正在识别意图…"})
    await asyncio.sleep(0.15)

    q = query.lower()
    if "任务" in query:
        yield _sse(
            {
                "event_type": "tool_call",
                "tool_name": "call_dify_app",
                "params": {"dify_app_id": "task-list", "query": query},
            }
        )
        tasks = db.query(SitTaskInfo).all()
        payload = {
            "type": "task_list",
            "data": {
                "tasks": [
                    {
                        "id": t.id,
                        "name": t.name,
                        "status": t.status,
                        "start_time": t.start_time.isoformat(),
                        "end_time": t.end_time.isoformat(),
                    }
                    for t in tasks
                ]
            },
        }
        db.add(AiToolCall(session_id=session_id, tool_name="call_dify_app", summary="任务列表查询"))
        db.commit()
        yield _sse({"event_type": "tool_result", "content": "Dify 返回任务列表", "business_payload": payload})
        yield _sse(
            {
                "event_type": "answer",
                "content": "已打开当前任务列表。",
                "business_payload": payload,
            }
        )
        return

    if "态势" in query or "飞机" in query or "realtime" in q:
        yield _sse(
            {
                "event_type": "tool_call",
                "tool_name": "call_dify_app",
                "params": {"dify_app_id": "situation-query", "query": query},
            }
        )
        rows = db.query(SitAircraftPoint).order_by(SitAircraftPoint.observed_at.desc()).limit(20).all()
        latest = {}
        for row in rows:
            latest.setdefault(row.aircraft_id, row)
        payload = {
            "type": "aircraft_situation",
            "data": {
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
            },
        }
        db.add(AiToolCall(session_id=session_id, tool_name="call_dify_app", summary="态势查询"))
        db.commit()
        yield _sse({"event_type": "tool_result", "content": "Dify 返回态势点位", "business_payload": payload})
        yield _sse(
            {
                "event_type": "answer",
                "content": "已查询到态势信息，三维球已标绘飞机点位。",
                "business_payload": payload,
            }
        )
        return

    yield _sse(
        {
            "event_type": "answer",
            "content": "当前指令不在态势/任务垂域内。你可以试试：查询实时态势信息，或显示当前任务列表。",
        }
    )


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _capture_answer(chunk: str) -> str:
    for line in chunk.splitlines():
        if not line.startswith("data:"):
            continue
        try:
            obj = json.loads(line[5:].strip())
        except json.JSONDecodeError:
            continue
        if obj.get("event_type") == "answer":
            return str(obj.get("content") or "")
    return ""


async def _harness_sse(
    db: Session,
    session_id: str,
    query: str,
    task_id: str | None = None,
    done: str | None = None,
):
    url = f"{settings.harness_base_url.rstrip('/')}/v1/chat/stream"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=120.0)) as client:
            params = {"session_id": session_id, "q": query}
            if task_id:
                params["task_id"] = task_id
            if done:
                params["done"] = done
            async with client.stream("GET", url, params=params) as resp:
                if resp.status_code >= 400:
                    body = (await resp.aread()).decode("utf-8", errors="replace")
                    yield _sse(
                        {
                            "event_type": "answer",
                            "content": f"Harness 返回 {resp.status_code}：{body[:240]}",
                        }
                    )
                    return
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    yield f"data: {raw}\n\n"
                    try:
                        obj = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("event_type") == "tool_result":
                        db.add(
                            AiToolCall(
                                session_id=session_id,
                                tool_name=obj.get("tool_name") or "call_dify_app",
                                summary=str(obj.get("content") or "")[:240],
                            )
                        )
                        db.commit()
    except httpx.HTTPError as exc:
        yield _sse(
            {
                "event_type": "answer",
                "content": f"无法连接 Harness（{settings.harness_base_url}）：{exc}",
            }
        )


@router.get("/chat/stream")
async def chat_stream(
    session_id: str = Query(...),
    q: str = Query(...),
    task_id: str | None = Query(default=None),
    done: str | None = Query(default=None, description="前端已完成行为 id，逗号分隔"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    db.add(AiChatMessage(session_id=session_id, role="user", content=q))
    db.commit()

    async def event_gen():
        answer_text = ""
        if settings.use_mock_ai:
            async for chunk in _mock_sse(db, session_id, q):
                answer_text = _capture_answer(chunk) or answer_text
                yield chunk
        else:
            async for chunk in _harness_sse(db, session_id, q, task_id, done):
                answer_text = _capture_answer(chunk) or answer_text
                yield chunk
        db.add(AiChatMessage(session_id=session_id, role="assistant", content=answer_text or "stream-completed"))
        db.commit()

    return StreamingResponse(event_gen(), media_type="text/event-stream")
