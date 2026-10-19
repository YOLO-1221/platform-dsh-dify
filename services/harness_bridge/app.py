"""SSE bridge FastAPI expects for platform chat.

Default listen :3081 (true `dsh web` usually owns :3080).
  GET /v1/chat/stream?session_id=&q=
Events: thinking, tool_call, tool_result, answer.

Route: registry keywords → Dify (Agent/Workflow with stored API Key).
No keyword match → DeepSeek chat reply (no local-llm fallback).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse

app = FastAPI(title="platform2-harness-bridge")

_REPO_ROOT = Path(__file__).resolve().parents[2]
DIFY_BASE = os.environ.get("PLATFORM2_DIFY_BASE", "http://127.0.0.1:5001").rstrip("/")
PLATFORM_API = os.environ.get("PLATFORM2_API_BASE", "http://127.0.0.1:8000").rstrip("/")
SERVICE_TOKEN = os.environ.get("PLATFORM2_SERVICE_TOKEN", "platform2-dify-local")
def _credential_candidates() -> list[Path]:
    homes: list[Path] = []
    env_home = os.environ.get("DSH_HOME", "").strip()
    if env_home:
        homes.append(Path(env_home))
    homes.append(_REPO_ROOT / ".dsh-home")
    homes.append(Path.home() / ".dsh")
    return [h / ".credentials.yaml" for h in homes]


def _load_credential_refs() -> dict[str, str]:
    refs: dict[str, str] = {}
    for path in _credential_candidates():
        if not path.is_file():
            continue
        try:
            import yaml

            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            raw = data.get("refs") or {}
            if isinstance(raw, dict):
                for key, value in raw.items():
                    if isinstance(value, str) and value.strip() and key not in refs:
                        refs[key] = value.strip()
        except Exception:
            # flat fallback: KEY: value lines
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if ":" not in stripped:
                    continue
                key, value = stripped.split(":", 1)
                key, value = key.strip(), value.strip().strip("'\"")
                if key.endswith("_API_KEY") and value and key not in refs:
                    refs[key] = value
    return refs


def _resolve_llm() -> tuple[str, str, str]:
    """Return (base_url, api_key, model). Prefer explicit env, then DeepSeek, then GLM."""
    refs = _load_credential_refs()
    explicit_key = os.environ.get("PLATFORM2_LLM_API_KEY", "").strip()
    explicit_base = os.environ.get("PLATFORM2_LLM_BASE_URL", "").strip()
    explicit_model = os.environ.get("PLATFORM2_LLM_MODEL", "").strip()
    if explicit_key and explicit_base:
        return (
            explicit_base.rstrip("/"),
            explicit_key,
            explicit_model or "gpt-4o-mini",
        )

    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip() or refs.get("DEEPSEEK_API_KEY", "")
    if deepseek_key:
        return (
            os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").rstrip("/"),
            deepseek_key,
            os.environ.get("DSH_MODEL", "deepseek-chat"),
        )

    glm_key = os.environ.get("GLM_API_KEY", "").strip() or refs.get("GLM_API_KEY", "")
    if glm_key:
        return (
            os.environ.get("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip("/"),
            glm_key,
            os.environ.get("GLM_MODEL", "glm-4.7-flash"),
        )
    return ("", "", "")


LLM_BASE, LLM_KEY, LLM_MODEL = _resolve_llm()
LLM_PROVIDER = (
    "deepseek"
    if "deepseek" in LLM_BASE
    else "glm"
    if "bigmodel" in LLM_BASE
    else ("custom" if LLM_KEY else "none")
)


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _split_keywords(text: str) -> list[str]:
    parts = text.replace("，", ",").replace("、", ",").replace(";", ",").split(",")
    return [part.strip() for part in parts if part.strip()]


_LEADING = ("查询", "查", "显示", "问")


def _keyword_matches(word: str, query: str) -> bool:
    """True when the keyword occurs in the query, or after a leading verb.

    「查态势」因此能命中「我要查询实时态势信息」。
    """
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


def _keyword_route(query: str, apps: list[dict]) -> dict[str, Any] | None:
    best: tuple[int, dict[str, Any]] | None = None
    for app_row in apps:
        if not app_row.get("enabled", True):
            continue
        words = _split_keywords(str(app_row.get("keywords") or ""))
        if not words:
            words = _split_keywords(str(app_row.get("intent_desc") or ""))
        for word in words:
            if _keyword_matches(word, query) and (best is None or len(word) > best[0]):
                best = (len(word), app_row)
    return None if best is None else best[1]


async def _chat_completions(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.3,
) -> tuple[str | None, str]:
    if not LLM_KEY or not LLM_BASE:
        return None, "none"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            resp = await client.post(
                f"{LLM_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_KEY}"},
                json={"model": LLM_MODEL, "messages": messages, "temperature": temperature},
            )
        if resp.status_code == 402:
            return None, f"{LLM_PROVIDER}_balance"
        if resp.status_code >= 400:
            return None, f"{LLM_PROVIDER}_{resp.status_code}"
        text = str(resp.json()["choices"][0]["message"]["content"] or "").strip()
        if text:
            return text, LLM_PROVIDER
    except Exception:
        return None, f"{LLM_PROVIDER}_error"
    return None, "none"


async def _load_apps() -> list[dict]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{PLATFORM_API}/api/v1/internal/dify/apps",
            headers={"Authorization": f"Bearer {SERVICE_TOKEN}"},
        )
        resp.raise_for_status()
        return list(resp.json().get("items") or [])


async def _consume_dify_sse(resp: httpx.Response) -> str:
    """Agent apps only allow streaming; collect answer from SSE chunks.

    Agent emits both `agent_message` and `message` with the same text — prefer
    agent_message; fall back to message for chat/chatflow apps.
    """
    agent_chunks: list[str] = []
    message_chunks: list[str] = []
    async for line in resp.aiter_lines():
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


async def _run_dify(app: dict[str, Any], query: str) -> dict[str, Any]:
    api_key = str(app.get("api_key") or "").strip()
    if not api_key:
        raise RuntimeError(f"应用 {app.get('app_id')} 未配置 API Key")
    headers = {"Authorization": f"Bearer {api_key}"}
    app_type = str(app.get("app_type") or "workflow")
    async with httpx.AsyncClient(timeout=120.0) as client:
        if app_type == "agent":
            async with client.stream(
                "POST",
                f"{DIFY_BASE}/v1/chat-messages",
                headers=headers,
                json={
                    "inputs": {},
                    "query": query,
                    "response_mode": "streaming",
                    "user": "platform2",
                },
            ) as resp:
                if resp.status_code >= 400:
                    body = (await resp.aread()).decode("utf-8", errors="replace")
                    raise RuntimeError(f"Dify Agent {resp.status_code}: {body[:300]}")
                answer = await _consume_dify_sse(resp)
            return {"answer": answer or "Agent 无文本回复", "business_payload": None}
        resp = await client.post(
            f"{DIFY_BASE}/v1/workflows/run",
            headers=headers,
            json={"inputs": {"query": query}, "response_mode": "blocking", "user": "platform2"},
        )
        resp.raise_for_status()
        data = resp.json().get("data") or {}
        outputs = data.get("outputs") or {}
        if not isinstance(outputs, dict):
            return {"answer": str(outputs), "business_payload": None}
        return outputs


async def _llm_reply(query: str) -> tuple[str | None, str]:
    system = (
        "你是三维空域态势平台的对话助手。"
        "用中文简洁回答用户问题。"
        "若涉及实时态势点位或任务列表，提示用户说：查询实时态势信息，或显示当前任务列表。"
    )
    return await _chat_completions(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": query},
        ]
    )


def _llm_unavailable_message(provider: str) -> str:
    if provider.endswith("_balance"):
        return "大模型余额不足，请充值或检查 API Key。"
    if provider.endswith("_429"):
        return "大模型当前访问量过大，请稍后再试。"
    if provider not in {"none", ""}:
        return f"大模型调用失败（{provider}）。请检查密钥与网络。"
    return "未配置大模型密钥（DEEPSEEK_API_KEY / GLM_API_KEY，或 .dsh-home/.credentials.yaml refs）。"


def _infer_business_kind(query: str, app: dict[str, Any] | None = None) -> str | None:
    """Map utterance / registry row to platform business payload type."""
    blob = " ".join(
        [
            query,
            str((app or {}).get("app_id") or ""),
            str((app or {}).get("name") or ""),
            str((app or {}).get("keywords") or ""),
            str((app or {}).get("intent_desc") or ""),
        ]
    ).lower()
    if any(k in blob for k in ("任务", "检测", "航迹", "时间轴", "task")):
        return "task_list"
    if any(k in blob for k in ("态势", "飞机", "点位", "空域", "realtime", "aircraft", "situation")):
        return "aircraft_situation"
    return None


async def _fetch_platform_payload(kind: str) -> dict[str, Any] | None:
    headers = {"Authorization": f"Bearer {SERVICE_TOKEN}"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        if kind == "aircraft_situation":
            resp = await client.get(
                f"{PLATFORM_API}/api/v1/internal/situation/aircraft/realtime",
                headers=headers,
            )
            resp.raise_for_status()
            points = resp.json().get("points") or []
            return {
                "type": "aircraft_situation",
                "data": {"points": points},
                "answer": f"已查询到 {len(points)} 架飞机的态势点位。",
            }
        if kind == "task_list":
            resp = await client.get(
                f"{PLATFORM_API}/api/v1/internal/situation/task/list",
                headers=headers,
            )
            resp.raise_for_status()
            tasks = resp.json().get("tasks") or []
            return {
                "type": "task_list",
                "data": {"tasks": tasks},
                "answer": f"当前共 {len(tasks)} 个检测任务。",
            }
    return None


async def _ensure_business_payload(
    query: str,
    app: dict[str, Any] | None,
    outputs: dict[str, Any],
) -> dict[str, Any]:
    """Attach platform points/tasks when Dify Agent only returns plain text."""
    payload = outputs.get("business_payload")
    if isinstance(payload, dict) and payload.get("type"):
        return outputs
    kind = _infer_business_kind(query, app)
    if not kind:
        return outputs
    try:
        fetched = await _fetch_platform_payload(kind)
    except Exception:
        return outputs
    if not fetched:
        return outputs
    merged = dict(outputs)
    merged["business_payload"] = {"type": fetched["type"], "data": fetched["data"]}
    answer = str(merged.get("answer") or "").strip()
    if not answer or answer in {"工作流已完成。", "Agent 无文本回复"}:
        merged["answer"] = fetched["answer"]
    elif fetched["type"] == "aircraft_situation":
        points = fetched["data"].get("points") or []
        merged["answer"] = f"{answer}\n（已加载 {len(points)} 个态势点位到三维球）"
    elif fetched["type"] == "task_list":
        tasks = fetched["data"].get("tasks") or []
        merged["answer"] = f"{answer}\n（已打开 {len(tasks)} 个检测任务）"
    return merged


async def stream_chat(session_id: str, query: str) -> AsyncIterator[str]:
    yield _sse({"event_type": "thinking", "content": "正在连接智能体…", "session_id": session_id})
    try:
        apps = await _load_apps()
    except Exception as exc:
        yield _sse({"event_type": "answer", "content": f"无法读取 Dify 注册表：{exc}"})
        return

    hit = _keyword_route(query, apps)
    if not hit:
        # 未登记关键字时，若话术本身是态势/任务，直接拉平台业务数据，避免卡在大模型。
        kind = _infer_business_kind(query)
        if kind:
            try:
                fetched = await _fetch_platform_payload(kind)
            except Exception as exc:
                yield _sse({"event_type": "answer", "content": f"平台业务查询失败：{exc}"})
                return
            if fetched:
                payload = {"type": fetched["type"], "data": fetched["data"]}
                yield _sse(
                    {
                        "event_type": "tool_result",
                        "content": "平台业务数据",
                        "business_payload": payload,
                        "tool_name": "platform_situation",
                    }
                )
                yield _sse(
                    {
                        "event_type": "answer",
                        "content": fetched["answer"],
                        "business_payload": payload,
                        "provider": "platform",
                    }
                )
                return
        reply, provider = await _llm_reply(query)
        yield _sse(
            {
                "event_type": "answer",
                "content": reply or _llm_unavailable_message(provider),
                "provider": provider if reply else "none",
            }
        )
        return

    app_id = hit.get("app_id")
    yield _sse(
        {
            "event_type": "tool_call",
            "tool_name": "call_dify_app",
            "params": {"dify_app_id": app_id, "query": query},
        }
    )
    try:
        outputs = await _run_dify(hit, query)
        outputs = await _ensure_business_payload(query, hit, outputs)
    except Exception as exc:
        yield _sse({"event_type": "answer", "content": f"Dify 调用失败：{exc}"})
        return

    payload = outputs.get("business_payload")
    answer = str(outputs.get("answer") or "工作流已完成。")
    yield _sse(
        {
            "event_type": "tool_result",
            "content": "Dify 返回结果",
            "business_payload": payload,
            "tool_name": "call_dify_app",
        }
    )
    yield _sse(
        {
            "event_type": "answer",
            "content": answer,
            "business_payload": payload,
            "provider": "dify",
        }
    )


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "harness-bridge",
        "llm_key": bool(LLM_KEY),
        "llm_provider": LLM_PROVIDER,
        "llm_base": LLM_BASE,
        "llm_model": LLM_MODEL,
        "dify_base": DIFY_BASE,
    }


@app.get("/v1/chat/stream")
async def chat_stream(session_id: str = Query(...), q: str = Query(...)):
    return StreamingResponse(stream_chat(session_id, q), media_type="text/event-stream")
