"""OpenAI-compatible local agent for platform2 when DeepSeek balance is unavailable."""

from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="platform2-local-llm")


class Msg(BaseModel):
    role: str
    content: str


class ChatBody(BaseModel):
    model: str = "platform2-local-agent"
    messages: list[Msg] = Field(default_factory=list)
    temperature: float = 0.3
    max_tokens: int | None = None


def _last_user(messages: list[Msg]) -> str:
    for m in reversed(messages):
        if m.role == "user":
            return m.content
    return ""


def _reply(messages: list[Msg]) -> str:
    user = _last_user(messages)
    # Intent router prompt used by harness_bridge
    if "只输出 JSON" in user and "可用工作流" in user:
        q = user
        m = re.search(r"用户指令：(.+)$", user, re.S)
        if m:
            q = m.group(1).strip()
        app_id = None
        if any(k in q for k in ("任务", "检测", "航迹", "时间轴", "task")):
            app_id = "task-list"
        elif any(k in q for k in ("态势", "飞机", "点位", "空域", "realtime", "aircraft", "situation")):
            app_id = "situation-query"
        return json.dumps({"app_id": app_id, "reason": "local-agent"}, ensure_ascii=False)

    if "工作流结果：" in user:
        note = user.split("工作流结果：", 1)[-1].split("\n", 1)[0].strip()
        return note or "已完成业务查询。"

    q = user.strip()
    if any(k in q for k in ("你好", "您好", "hi", "hello", "你是谁")):
        return (
            "我是三维空域态势平台的本地智能体。"
            "可以帮你查询实时态势、查看检测任务列表，也可以回答平台相关问题。"
            "试试：「我要查询实时态势信息」或「显示当前任务列表」。"
        )
    if any(k in q for k in ("能做什么", "你会什么", "帮助", "功能")):
        return (
            "我可以：1）查询并标绘飞机态势；2）打开当前检测任务列表；"
            "3）说明平台操作。业务数据来自垂域工作流，不会编造坐标。"
        )
    if any(k in q for k in ("态势", "飞机", "点位")):
        return "如需态势点位，请直接说「查询实时态势信息」，我会调用态势查询工作流并把结果标到三维球。"
    if any(k in q for k in ("任务", "航迹", "时间轴")):
        return "如需任务与航迹，请说「显示当前任务列表」，我会打开任务面板并加载时间轴。"
    return (
        f"已收到：「{q[:80]}」。"
        "当前使用本地智能体兜底（DeepSeek 余额不足或未配置时）。"
        "垂域指令可直接说：查询实时态势信息 / 显示当前任务列表。"
    )


@app.get("/health")
def health():
    return {"ok": True, "service": "local-llm", "model": "platform2-local-agent"}


@app.get("/v1/models")
def models():
    return {
        "object": "list",
        "data": [{"id": "platform2-local-agent", "object": "model", "owned_by": "platform2"}],
    }


@app.post("/v1/chat/completions")
def chat(body: ChatBody) -> dict[str, Any]:
    content = _reply(body.messages)
    return {
        "id": f"local-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.model or "platform2-local-agent",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
