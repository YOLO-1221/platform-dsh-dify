# LLM一键构建指令｜三维空域态势智能平台（完整独立项目，模块化可迁移）

> 与 `doc/PRD.md` V1.5 对齐。生成或改骨架时以 PRD 为准。

## 角色
你是全栈工程师，需要基于完整需求生成**可落地的项目骨架**：前端 Vue3+Vite+Pinia+Cesium，后端 FastAPI，SQLAlchemy，Alembic。
要求：完整独立、模块化低耦合；集成 DeepSeek Harness（`dsh`）与官方 Dify；支持对话 SSE。

## 整体需求概述
三维空域态势 Web 平台。业务：飞机态势查询、图像检测任务与航迹、vis-timeline 回放。AI：管理员在 `/admin/dify` 登记 Dify Agent/Workflow（关键字 + API Key）。平台对话走 harness-bridge `:3081`；`dsh web` 占 `:3080` 经 MCP `route_dify_message`。均按关键字调 Dify；未命中则大模型直接回答（默认 GLM `glm-4.7-flash`，无本地模型兜底）。界面操作与对话共用同一套业务 API。

## 业务规则
1. 飞机态势查询：实时 + 回溯。**进入查询模式后暂停实时点位自动刷新。**
2. 图像检测任务：多路并发；一期允许造数；同一任务时序检测点合批成航迹；vis-timeline 按帧吸附（参考 platform VisMissionTimeline）。
3. AI 调度（V1.5）：
    - 平台 SSE：FastAPI → harness-bridge `:3081`（`PLATFORM2_HARNESS_BASE_URL`）；勿指向 `dsh` `:3080`；
    - `dsh web` `:3080`：Web profile 挂载 MCP `scripts/dify-mcp`；
    - 关键字命中：Agent → `/v1/chat-messages`（仅 streaming）；Workflow → `/v1/workflows/run`（blocking）；
    - 无关键字命中：大模型直接答；无 API Key：返回未配置说明，不请求 Dify；无本地模型兜底；
4. SSE 事件：`thinking` / `tool_call` / `tool_result` / `answer`；可选 `business_payload`。
5. 双入口：界面表单/按钮 与 AI 对话，同一后端业务接口。

## 技术栈硬性约束
### 前端
Vue3 + Vite + PNPM；CesiumJS；Pinia；Element Plus；vis-timeline；Fetch REST + SSE。
`src/modules/`：`cesiumRender`、`situation`、`taskTrack`、`aiChat`。
管理页：`/admin/dify`（关键字、API Key、Agent/Workflow）、`/admin/logs`。

### 后端
FastAPI；SQLAlchemy 2.0；PostgreSQL；httpx；JWT。
路由：`/api/v1/auth`、`/api/v1/ai`、`/api/v1/admin/dify`、`/api/v1/situation`、`/api/v1/internal`（服务令牌，供 MCP 读注册表）。

### DeepSeek Harness / Dify
- Harness 源码：`deepseek-harness/`；启动：`scripts/dsh web` → `:3080`（默认 `DSH_HOME=.dsh-home`）
- 平台对话桥：`services/harness_bridge`；`scripts/start-ai-stack.sh` → `:3081`
- Dify 官方 Compose：`dify/`；宿主端口 **5001**；启动：`scripts/start-dify.sh`
- MCP：`services/dify_mcp/server.py`，入口 `scripts/dify-mcp`

### 数据库
基础表：`users`、`dify_agent_registry`（含 `keywords`、`api_key`）、`ai_chat_session`、`ai_chat_message`、`ai_tool_call`
业务表（`sit_`）：`sit_aircraft_point`、`sit_task_info`、`sit_task_image`、`sit_image_detection_result`、`sit_track`

## 页面清单
1. 登录页
2. 三维态势主页（Cesium、查询表单、时间轴、对话面板、任务窗、工具栏含 Dify 管理入口）
3. `/admin/dify` 垂域注册
4. `/admin/logs` 日志

## SSE 事件结构（必须严格遵守）
```json
{
  "event_type": "thinking",
  "content": "正在识别意图，准备调用态势查询工作流"
}
{
  "event_type": "tool_call",
  "tool_name": "call_dify_app",
  "params": {"dify_app_id": "xxx", "query": "实时态势查询"}
}
{
  "event_type": "tool_result",
  "content": "Dify返回结果",
  "business_payload": {
    "type": "aircraft_situation",
    "data": {"points": []}
  }
}
{
  "event_type": "answer",
  "content": "已查询到实时态势信息，三维球已标绘飞机点位。",
  "business_payload": {
    "type": "aircraft_situation",
    "data": {"points": []}
  }
}
```
