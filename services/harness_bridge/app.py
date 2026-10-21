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


def _strip_markdown_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if not lines:
        return stripped
    # drop opening ``` or ```json
    lines = lines[1:]
    while lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _candidate_json_blobs(text: str) -> list[str]:
    """Collect likely JSON object strings from an Agent reply."""
    cleaned = _strip_markdown_fence(text)
    blobs = [cleaned]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        blobs.append(cleaned[start : end + 1])
    return blobs


def _normalize_agent_outputs(obj: dict[str, Any], raw_text: str) -> dict[str, Any] | None:
    payload = obj.get("business_payload")
    if not isinstance(payload, dict) or not payload.get("type"):
        # allow {type, data} at top level
        if obj.get("type") and isinstance(obj.get("data"), (dict, list)):
            payload = {"type": obj["type"], "data": obj.get("data") or {}}
        else:
            return None
    answer = obj.get("answer")
    if answer is None or str(answer).strip() == "":
        answer = raw_text.strip() or f"已完成 {payload.get('type')}"
    business: dict[str, Any] = {
        "type": payload["type"],
        "data": payload.get("data") if isinstance(payload.get("data"), dict) else {"value": payload.get("data")},
    }
    next_actions = payload.get("next_actions")
    if next_actions is None:
        next_actions = obj.get("next_actions")
    if isinstance(next_actions, list):
        business["next_actions"] = next_actions
    return {"answer": str(answer), "business_payload": business}


def parse_agent_structured_reply(text: str) -> dict[str, Any] | None:
    """Parse Agent text into {answer, business_payload} when Skill returns JSON."""
    if not text or not text.strip():
        return None
    for blob in _candidate_json_blobs(text):
        try:
            obj = json.loads(blob)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            normalized = _normalize_agent_outputs(obj, text)
            if normalized is not None:
                return normalized
    return None


def _compose_agent_query(query: str, task_id: str | None = None, done: str | None = None) -> str:
    """把前端状态拼进 query，避免 Agent 未声明 inputs 时 400。"""
    parts: list[str] = []
    if task_id:
        parts.append(f"task_id={task_id}")
    if done:
        parts.append(f"done={done}")
    if not parts:
        return query
    return f"{query}\n\n[context] {'; '.join(parts)}"


def _parse_done_ids(done: str | None) -> list[str]:
    if not done:
        return []
    return [x.strip() for x in str(done).split(",") if x.strip()]


async def _run_dify(
    app: dict[str, Any],
    query: str,
    task_id: str | None = None,
    done: str | None = None,
) -> dict[str, Any]:
    api_key = str(app.get("api_key") or "").strip()
    if not api_key:
        raise RuntimeError(f"应用 {app.get('app_id')} 未配置 API Key")
    headers = {"Authorization": f"Bearer {api_key}"}
    app_type = str(app.get("app_type") or "workflow")
    inputs: dict[str, Any] = {"query": query}
    if task_id:
        inputs["task_id"] = task_id
    if done:
        inputs["done"] = done
    agent_query = _compose_agent_query(query, task_id, done)
    async with httpx.AsyncClient(timeout=120.0) as client:
        if app_type == "agent":
            async with client.stream(
                "POST",
                f"{DIFY_BASE}/v1/chat-messages",
                headers=headers,
                json={
                    "inputs": {},
                    "query": agent_query,
                    "response_mode": "streaming",
                    "user": "platform2",
                },
            ) as resp:
                if resp.status_code >= 400:
                    body = (await resp.aread()).decode("utf-8", errors="replace")
                    raise RuntimeError(f"Dify Agent {resp.status_code}: {body[:300]}")
                answer = await _consume_dify_sse(resp)
            parsed = parse_agent_structured_reply(answer)
            if parsed is not None:
                return parsed
            return {"answer": answer or "Agent 无文本回复", "business_payload": None}
        resp = await client.post(
            f"{DIFY_BASE}/v1/workflows/run",
            headers=headers,
            json={"inputs": inputs, "response_mode": "blocking", "user": "platform2"},
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
    """Map utterance / registry row to platform business payload type.

    Layer phrases are matched on the user text first so registry keywords
    such as 「检测」do not collapse every step into a task list.
    """
    q = query.lower()
    if any(k in q for k in ("关联态势", "时空关联")):
        return "associated_situation"
    if any(k in q for k in ("检测图像", "加载图像")):
        return "detection_images"
    if any(k in q for k in ("检测航迹", "加载航迹")):
        return "detection_tracks"
    if "检测点" in q:
        return "detection_points"
    if "打开任务" in q:
        return "task_open"
    if any(k in q for k in ("任务列表", "查询任务", "检测任务", "当前任务")):
        return "task_list"
    if any(k in q for k in ("态势", "飞机", "点位", "空域", "realtime", "aircraft", "situation")):
        return "aircraft_situation"
    blob = " ".join(
        [
            str((app or {}).get("app_id") or ""),
            str((app or {}).get("name") or ""),
            str((app or {}).get("keywords") or ""),
            str((app or {}).get("intent_desc") or ""),
        ]
    ).lower()
    if any(k in blob for k in ("任务", "task")):
        return "task_list"
    if any(k in blob for k in ("态势", "situation", "aircraft")):
        return "aircraft_situation"
    return None


_TASK_LAYER = {
    "task_open": ("", "已打开任务"),
    "detection_points": ("/detections", "已加载检测点"),
    "detection_tracks": ("/tracks", "已加载检测航迹"),
    "detection_images": ("/images", "已加载检测图像"),
    "associated_situation": ("/associated-situation", "已加载时空关联态势点"),
}

# 与 web/src/modules/taskTrack/actionCatalog.js 保持一致
_DEFAULT_NEXT_ACTIONS: dict[str, list[dict[str, str]]] = {
    "task_list": [{"id": "open_task", "label": "打开任务", "utterance": "打开任务"}],
    "task_open": [
        {"id": "load_points", "label": "加载检测点", "utterance": "加载检测点"},
        {"id": "load_tracks", "label": "加载检测航迹", "utterance": "加载检测航迹"},
    ],
    "detection_points": [
        {"id": "load_tracks", "label": "加载检测航迹", "utterance": "加载检测航迹"},
        {"id": "load_images", "label": "加载检测图像", "utterance": "加载检测图像"},
        {"id": "load_associated", "label": "加载时空关联态势点", "utterance": "加载时空关联态势点"},
    ],
    "detection_tracks": [
        {"id": "load_images", "label": "加载检测图像", "utterance": "加载检测图像"},
        {"id": "load_associated", "label": "加载时空关联态势点", "utterance": "加载时空关联态势点"},
    ],
    "detection_images": [
        {"id": "load_associated", "label": "加载时空关联态势点", "utterance": "加载时空关联态势点"},
        {"id": "load_points", "label": "加载检测点", "utterance": "加载检测点"},
    ],
    "associated_situation": [
        {"id": "load_tracks", "label": "加载检测航迹", "utterance": "加载检测航迹"},
        {"id": "load_images", "label": "加载检测图像", "utterance": "加载检测图像"},
    ],
}


def _filter_next_actions(
    actions: list[Any],
    done_ids: list[str] | None = None,
) -> list[dict[str, str]]:
    done = set(done_ids or [])
    out: list[dict[str, str]] = []
    for item in actions:
        if not isinstance(item, dict):
            continue
        aid = str(item.get("id") or "").strip()
        if aid and aid in done:
            continue
        utterance = str(item.get("utterance") or "").strip()
        if not utterance:
            continue
        out.append(
            {
                "id": aid or utterance,
                "label": str(item.get("label") or utterance),
                "utterance": utterance,
            }
        )
    return out


def _with_default_next_actions(
    payload: dict[str, Any],
    done_ids: list[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict) or not payload.get("type"):
        return payload
    enriched = dict(payload)
    if isinstance(payload.get("next_actions"), list) and payload["next_actions"]:
        enriched["next_actions"] = _filter_next_actions(payload["next_actions"], done_ids)
        return enriched
    defaults = _DEFAULT_NEXT_ACTIONS.get(str(payload["type"]))
    if not defaults:
        return enriched
    enriched["next_actions"] = _filter_next_actions(list(defaults), done_ids)
    return enriched


async def _resolve_task_id(client: httpx.AsyncClient, headers: dict[str, str], task_id: str | None) -> str | None:
    if task_id:
        return task_id
    resp = await client.get(f"{PLATFORM_API}/api/v1/internal/situation/task/list", headers=headers)
    resp.raise_for_status()
    tasks = resp.json().get("tasks") or []
    if not tasks:
        return None
    return str(tasks[0].get("id") or "") or None


async def _fetch_platform_payload(kind: str, task_id: str | None = None) -> dict[str, Any] | None:
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
        layer = _TASK_LAYER.get(kind)
        if layer is None:
            return None
        resolved = await _resolve_task_id(client, headers, task_id)
        if not resolved:
            return {
                "type": kind,
                "data": {},
                "answer": "没有可打开的检测任务。",
            }
        suffix, label = layer
        resp = await client.get(
            f"{PLATFORM_API}/api/v1/internal/situation/task/{resolved}{suffix}",
            headers=headers,
        )
        resp.raise_for_status()
        body = resp.json()
        count = body.get("count")
        if kind == "task_open":
            name = (body.get("task") or {}).get("name") or resolved
            answer = f"已打开任务 {name}。"
        elif count is None:
            answer = f"{label}。"
        else:
            answer = f"{label} {count} 条。"
        return {"type": kind, "data": body, "answer": answer}
    return None


async def _ensure_business_payload(
    query: str,
    app: dict[str, Any] | None,
    outputs: dict[str, Any],
    task_id: str | None = None,
    done_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Attach platform JSON when Dify Agent only returns plain text."""
    payload = outputs.get("business_payload")
    if isinstance(payload, dict) and payload.get("type"):
        outputs = dict(outputs)
        outputs["business_payload"] = _with_default_next_actions(payload, done_ids)
        return outputs
    kind = _infer_business_kind(query, app)
    if not kind:
        return outputs
    try:
        fetched = await _fetch_platform_payload(kind, task_id)
    except Exception:
        return outputs
    if not fetched:
        return outputs
    merged = dict(outputs)
    merged["business_payload"] = _with_default_next_actions(
        {"type": fetched["type"], "data": fetched["data"]},
        done_ids,
    )
    answer = str(merged.get("answer") or "").strip()
    if not answer or answer in {"工作流已完成。", "Agent 无文本回复"}:
        merged["answer"] = fetched["answer"]
    else:
        merged["answer"] = f"{answer}\n（{fetched['answer']}）"
    return merged


async def stream_chat(
    session_id: str,
    query: str,
    task_id: str | None = None,
    done: str | None = None,
) -> AsyncIterator[str]:
    done_ids = _parse_done_ids(done)
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
                fetched = await _fetch_platform_payload(kind, task_id)
            except Exception as exc:
                yield _sse({"event_type": "answer", "content": f"平台业务查询失败：{exc}"})
                return
            if fetched:
                payload = _with_default_next_actions(
                    {"type": fetched["type"], "data": fetched["data"]},
                    done_ids,
                )
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
        outputs = await _run_dify(hit, query, task_id, done)
        outputs = await _ensure_business_payload(query, hit, outputs, task_id, done_ids)
    except Exception as exc:
        yield _sse({"event_type": "answer", "content": f"Dify 调用失败：{exc}"})
        return

    payload = outputs.get("business_payload")
    if isinstance(payload, dict):
        payload = _with_default_next_actions(payload, done_ids)
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
async def chat_stream(
    session_id: str = Query(...),
    q: str = Query(...),
    task_id: str | None = Query(default=None),
    done: str | None = Query(default=None, description="前端已完成行为 id，逗号分隔"),
):
    return StreamingResponse(
        stream_chat(session_id, q, task_id, done),
        media_type="text/event-stream",
    )
