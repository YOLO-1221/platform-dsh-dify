"""Dify-compatible local workflow runner.

Implements the subset platform2 needs when Docker/Dify is unavailable:
POST /v1/workflows/run with Bearer app token.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="platform2-dify-local")

PLATFORM_API = os.environ.get("PLATFORM2_API_BASE", "http://127.0.0.1:8000")
SERVICE_TOKEN = os.environ.get("PLATFORM2_SERVICE_TOKEN", "platform2-dify-local")

# Dify app API keys map to registered workflow ids.
APP_KEYS = {
    os.environ.get("DIFY_KEY_SITUATION", "app-situation-query"): "situation-query",
    os.environ.get("DIFY_KEY_TASK", "app-task-list"): "task-list",
}


class WorkflowRun(BaseModel):
    inputs: dict[str, Any] = {}
    response_mode: str = "blocking"
    user: str = "platform2"


def _auth_app(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    app_id = APP_KEYS.get(token)
    if not app_id:
        raise HTTPException(status_code=401, detail="unknown app key")
    return app_id


@app.get("/health")
def health():
    return {"ok": True, "service": "dify-local", "apps": list(APP_KEYS.values())}


@app.post("/v1/workflows/run")
def run_workflow(body: WorkflowRun, authorization: str | None = Header(default=None)):
    app_id = _auth_app(authorization)
    headers = {"Authorization": f"Bearer {SERVICE_TOKEN}"}
    query = str(body.inputs.get("query") or "")
    aircraft_id = body.inputs.get("aircraft_id")

    with httpx.Client(base_url=PLATFORM_API, timeout=20.0) as client:
        if app_id == "situation-query":
            resp = client.get("/api/v1/internal/situation/aircraft/realtime", headers=headers)
            resp.raise_for_status()
            points = resp.json().get("points", [])
            if aircraft_id:
                points = [p for p in points if p.get("aircraft_id") == aircraft_id]
            payload = {"type": "aircraft_situation", "data": {"points": points}}
            answer = f"已查询到 {len(points)} 架飞机的态势点位。"
        elif app_id == "task-list":
            resp = client.get("/api/v1/internal/situation/task/list", headers=headers)
            resp.raise_for_status()
            tasks = resp.json().get("tasks", [])
            payload = {"type": "task_list", "data": {"tasks": tasks}}
            answer = f"当前共 {len(tasks)} 个检测任务。"
        else:
            raise HTTPException(status_code=404, detail="workflow not installed")

    return {
        "workflow_run_id": f"local-{app_id}",
        "task_id": f"local-{app_id}",
        "data": {
            "id": f"local-{app_id}",
            "workflow_id": app_id,
            "status": "succeeded",
            "outputs": {
                "answer": answer,
                "business_payload": payload,
                "query": query,
            },
            "error": None,
        },
    }
