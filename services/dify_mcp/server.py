"""stdio MCP server: keyword-route a user utterance to a registered Dify app.

dsh launches this process. Tools:
  route_dify_message — match keywords, call Dify when hit
  list_dify_agents — enabled apps without API keys
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import httpx

API_BASE = os.environ.get("PLATFORM2_API_BASE", "http://127.0.0.1:8000").rstrip("/")
DIFY_BASE = os.environ.get("PLATFORM2_DIFY_BASE", "http://127.0.0.1:5001").rstrip("/")
SERVICE_TOKEN = os.environ.get("PLATFORM2_SERVICE_TOKEN", "platform2-dify-local")

TOOLS = [
    {
        "name": "route_dify_message",
        "description": (
            "回答用户前必须先调用本工具，把用户原话作为 query。"
            "matched 为 true 时只使用返回的 answer，不要自行编造态势或任务数据。"
            "matched 为 false 时再由你直接回答。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "用户原话"}},
            "required": ["query"],
        },
    },
    {
        "name": "list_dify_agents",
        "description": "列出已启用的 Dify 智能体或工作流及其关键字，不含 API Key。",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _read_message() -> dict[str, Any] | None:
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line.strip():
            return json.loads(line.decode("utf-8"))


def _write_message(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _split_keywords(text: str) -> list[str]:
    parts = text.replace("，", ",").replace("、", ",").replace(";", ",").split(",")
    return [part.strip() for part in parts if part.strip()]


def _load_apps() -> list[dict[str, Any]]:
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(
            f"{API_BASE}/api/v1/internal/dify/apps",
            headers={"Authorization": f"Bearer {SERVICE_TOKEN}"},
        )
        resp.raise_for_status()
        return list(resp.json().get("items") or [])


_LEADING = ("查询", "查", "显示", "问")


def _keyword_matches(word: str, query: str) -> bool:
    q = query.lower()
    w = word.lower()
    if not w:
        return False
    if w in q:
        return True
    for prefix in _LEADING:
        if w.startswith(prefix):
            rest = w[len(prefix) :].strip()
            if len(rest) >= 2 and rest in q:
                return True
    return False


def _match(query: str, apps: list[dict[str, Any]]) -> dict[str, Any] | None:
    best: tuple[int, dict[str, Any]] | None = None
    for app in apps:
        if not app.get("enabled", True):
            continue
        words = _split_keywords(str(app.get("keywords") or ""))
        if not words:
            words = _split_keywords(str(app.get("intent_desc") or ""))
        for word in words:
            if _keyword_matches(word, query) and (best is None or len(word) > best[0]):
                best = (len(word), app)
    return None if best is None else best[1]


def _consume_dify_sse(resp: httpx.Response) -> str:
    agent_chunks: list[str] = []
    message_chunks: list[str] = []
    for line in resp.iter_lines():
        if not line.startswith("data:"):
            continue
        raw = line[5:].strip()
        if not raw or raw == "[DONE]":
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        kind = str(event.get("event") or "")
        piece = event.get("answer")
        if kind == "agent_message" and piece:
            agent_chunks.append(str(piece))
        elif kind == "message" and piece:
            message_chunks.append(str(piece))
        elif kind == "error":
            raise RuntimeError(str(event.get("message") or event))
    return "".join(agent_chunks or message_chunks).strip()


def _call_dify(app: dict[str, Any], query: str) -> str:
    api_key = str(app.get("api_key") or "").strip()
    if not api_key:
        return f"应用 {app.get('app_id')} 未配置 API Key，无法调用 Dify。"
    headers = {"Authorization": f"Bearer {api_key}"}
    app_type = str(app.get("app_type") or "workflow")
    with httpx.Client(timeout=120.0) as client:
        if app_type == "agent":
            with client.stream(
                "POST",
                f"{DIFY_BASE}/v1/chat-messages",
                headers=headers,
                json={
                    "inputs": {},
                    "query": query,
                    "response_mode": "streaming",
                    "user": "dsh",
                },
            ) as resp:
                if resp.status_code >= 400:
                    body = resp.read().decode("utf-8", errors="replace")
                    raise RuntimeError(f"Dify Agent {resp.status_code}: {body[:300]}")
                answer = _consume_dify_sse(resp)
            return answer or "Agent 无文本回复"
        resp = client.post(
            f"{DIFY_BASE}/v1/workflows/run",
            headers=headers,
            json={"inputs": {"query": query}, "response_mode": "blocking", "user": "dsh"},
        )
        resp.raise_for_status()
        data = resp.json().get("data") or {}
        outputs = data.get("outputs") or {}
        if isinstance(outputs, dict) and outputs.get("answer"):
            return str(outputs["answer"])
        return json.dumps(outputs, ensure_ascii=False)


def _tool_result(text: str, *, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "list_dify_agents":
        apps = [
            {
                "app_id": app.get("app_id"),
                "name": app.get("name"),
                "app_type": app.get("app_type"),
                "keywords": app.get("keywords") or app.get("intent_desc"),
            }
            for app in _load_apps()
            if app.get("enabled", True)
        ]
        return _tool_result(json.dumps(apps, ensure_ascii=False))
    if name == "route_dify_message":
        query = str(arguments.get("query") or "").strip()
        if not query:
            return _tool_result("缺少 query", is_error=True)
        apps = _load_apps()
        hit = _match(query, apps)
        if hit is None:
            return _tool_result(json.dumps({"matched": False}, ensure_ascii=False))
        try:
            answer = _call_dify(hit, query)
        except Exception as exc:
            return _tool_result(
                json.dumps(
                    {"matched": True, "app_id": hit.get("app_id"), "error": str(exc)},
                    ensure_ascii=False,
                ),
                is_error=True,
            )
        return _tool_result(
            json.dumps(
                {
                    "matched": True,
                    "app_id": hit.get("app_id"),
                    "name": hit.get("name"),
                    "answer": answer,
                },
                ensure_ascii=False,
            )
        )
    return _tool_result(f"未知工具 {name}", is_error=True)


def _handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    msg_id = message.get("id")
    if method == "notifications/initialized" or msg_id is None and str(method).startswith("notifications/"):
        return None
    if method == "initialize":
        params = message.get("params") or {}
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": params.get("protocolVersion") or "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "platform2-dify", "version": "0.1.0"},
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = message.get("params") or {}
        try:
            result = _call_tool(str(params.get("name") or ""), dict(params.get("arguments") or {}))
        except Exception as exc:
            result = _tool_result(str(exc), is_error=True)
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}
    if msg_id is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"method not found: {method}"},
    }


def main() -> None:
    while True:
        message = _read_message()
        if message is None:
            return
        response = _handle(message)
        if response is not None:
            _write_message(response)


if __name__ == "__main__":
    main()
