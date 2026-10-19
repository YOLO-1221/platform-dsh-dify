# PRD V1.5｜三维空域态势智能平台（全新独立完整项目，内置 DeepSeek Harness + Cesium，支持模块化迁移）
> 文件路径：/Users/yolo/project/VueProject/2026/platform2/doc/PRD.md
> 版本：V1.5
> 日期：2026-10-16
> 状态：与当前实现同步（双入口对话、关键字路由、无本地模型兜底）
> 核心说明：
本项目为**全新完整独立项目**，所有能力全部自建：Cesium三维地球、空域态势业务、图像检测任务航迹、时间轴、DeepSeek Harness对话调度 + Dify垂域工作流。
架构设计上**从一开始就考虑模块解耦、可移植**，未来可整体/分模块迁移至其他项目。
不依赖任何外部已有主项目底座，项目本身完整可独立部署运行。

## 1. 文档概述
### 1.1 产品简介
三维空域态势智能平台，一套完整独立Web系统。前端Vue3+Cesium构建三维地球可视化；后端FastAPI；集成DeepSeek Harness作为AI智能体调度引擎，搭配Dify构建垂域工作流。
系统两大业务主线：飞机空域态势标绘查询、图像检测任务航迹生成与时间轴回放；同时提供AI自然语言对话交互能力。用户可界面按钮/表单操作，也可以对话输入指令；**平台内对话**与 **`dsh` Web** 两条入口均按注册表关键字路由到 Dify，未命中则由大模型直接文本回答。

业务主线：
1. **飞机态势信息查询**：支持实时飞机点位接收、历史态势回溯查询；进入查询模式后，暂停实时点位自动更新，查询结果标绘在三维地球。
2. **图像检测任务处理与航迹展示**：支持多路并发实时任务推送图片；图片送入图像检测算法服务得到单图飞机检测点；后端对同任务时序检测点合批生成航迹；基于任务起始时间、图片接收时间生成时间轴，支持拖拽时间轴回溯图像与航迹。

AI对话交互（双入口，同一套关键字与 Dify 注册表）：
1. **平台前端对话面板**：SSE → FastAPI → **harness-bridge（:3081）** → 关键字命中则调 Dify，否则调大模型。
2. **`dsh web`（:3080）**：提问前经 MCP `route_dify_message` 读注册表；命中则调 Dify，否则由 dsh 绑定的大模型直接回答。
3. 命中后返回文本及可选结构化业务数据，驱动 Cesium 标绘与任务窗口。

### 1.2 设计原则（迁移友好，可扩展）
1. **模块化分层，低耦合**
    - 前端：Cesium渲染模块、态势业务模块、任务航迹模块、AI对话模块互相独立，目录隔离，可单独抽取迁移。
    - 后端：业务路由分组隔离；AI调度服务、态势业务服务分层；数据表统一前缀，业务表与基础表隔离。
2. **接口标准化**
    - AI对话SSE事件结构统一；业务API使用标准REST；结构化业务数据定义固定JSON Schema，便于迁移复用。
3. **组件化、可插拔**
    - 标绘工具、时间轴、任务窗口、对话面板均封装为独立组件；
    - Dify垂域配置、DeepSeek Harness提示词可导出，迁移时直接复用。
4. **完整独立可部署**
    项目自带全部底座：登录鉴权、Cesium、对话SSE、DeepSeek Harness、Dify调用、态势业务，不需要依赖外部项目。迁移时可整体迁移，也可拆分模块迁移。

### 1.3 目标用户
1. **态势操作员**：三维地球浏览空域态势、表单查询态势、查看检测任务、时间轴回放、AI对话下发自然语言指令。
2. **平台管理员**：用户管理、Dify垂域应用注册管理、查看对话日志、态势/任务日志。

### 1.4 项目范围
✅ 一期全部新建内容
1. 前端
    - Cesium三维地球底座，相机控制、图层管理
    - 飞机点位标绘、航迹标绘工具类
    - 态势查询表单组件
    - 任务列表悬浮工具窗口
    - 图片时间轴组件
    - AI对话面板（输入框、对话历史、思考/工具调用展示面板）
    - Pinia全局状态：地图状态、态势状态、任务状态、对话状态
    - 用户登录页面

2. 后端 FastAPI
    - 用户登录、JWT鉴权模块
    - AI对话SSE流式接口，转发至 harness-bridge
    - Dify垂域应用管理接口（注册表CRUD；管理员角色）
    - 态势业务接口组 `/api/v1/situation`
    - 任务、图片、检测点、航迹业务接口
    - 数据库模型、Alembic迁移脚本

3. DeepSeek Harness（`dsh`）与 harness-bridge
    - 本仓库 `deepseek-harness/`，CLI 为 `scripts/dsh`，默认 `DSH_HOME` 为仓库 `.dsh-home`
    - **`dsh web` :3080**：真 Harness Web UI；Web profile 挂载 MCP `platform2-dify`（`scripts/dify-mcp`）
    - **harness-bridge :3081**：平台对话专用 SSE 适配层（`services/harness_bridge`）；**不与 `dsh web` 抢端口**
    - 工具 `route_dify_message`：用用户原话匹配注册表关键字，命中后调用 Dify
    - 工具 `list_dify_agents`：列出已启用应用（不含 API Key）
    - 默认大模型与 dsh 对齐：GLM `glm-4.7-flash`（`open.bigmodel.cn`）；亦可配置 DeepSeek。**无本地模型兜底**

4. Dify
    - 官方 Compose 部署在 `dify/`，控制台与 API 入口为宿主 `http://127.0.0.1:5001`
    - 应用在 Dify 控制台创建；在平台管理页登记后才可按关键字调用
    - 预置登记：态势查询（关键字含态势/飞机/点位/空域）、任务列表（关键字含任务/检测/航迹/时间轴）；须填写对应 API Key 后才会真正请求 Dify

5. 数据库PostgreSQL
    - 基础表：用户、Dify注册表、对话会话、对话消息、工具调用日志
    - 业务表：`sit_`前缀，态势点位、任务、图片、检测点、航迹

❌ 一期不包含
1. 全链路监控告警
2. 海量三维数据加载优化（LOD、瓦片）二期扩展
3. 多租户隔离（二期）

## 2. 业务需求
### 2.1 业务流程一：飞机态势查询（实时/回溯）
触发入口二选一：界面表单提交 / AI对话指令（例：`我要查询实时态势信息`）
1. 用户发起态势查询；
2. AI链路：关键字命中「态势查询」应用 → 调用对应 Dify Agent/Workflow → 组装查询参数，调用后端态势查询接口；界面操作直接调用后端接口，不走AI链路；
3. 系统进入**查询模式**：暂停实时点位流自动刷新；
4. 后端返回飞机点位结构化数据；前端Cesium标绘点位；
5. 用户手动点击“恢复实时”，退出查询模式，继续接收实时点位推送。

> 约束：**查询模式下，不会自动更新实时飞机点位**。

### 2.2 业务流程二：图像检测任务接收、检测、航迹展示（实时/回溯）
触发入口：界面按钮 / AI对话指令（例：`显示当前任务列表`）
1. 后台持续接收多路并发任务推送图片；
2. 图片提交至外部图像检测算法服务，每张图片返回一组飞机检测点；
3. 后端对**同一任务、时序连续检测点做合批处理**，生成连续航迹；
4. 后端基于任务开始时间、每张图片接收时间，生成时间轴元数据；前端渲染时间轴；
5. 用户拖拽时间轴，选定时间戳，三维球加载对应时刻航迹与图片；
6. 唤起任务列表工具窗口，展示全部任务；选中任务查看对应航迹与图像。

### 2.3 AI对话调度完整流程
#### 2.3.1 平台前端对话（FastAPI → harness-bridge）
1. 用户在平台对话面板输入自然语言，提交；
2. 前端发起 SSE：`GET /api/v1/ai/chat/stream`（需先 `POST /api/v1/ai/chat/session`），携带会话 ID，JWT 鉴权；
3. FastAPI 转发至 harness-bridge：`GET {PLATFORM2_HARNESS_BASE_URL}/v1/chat/stream`（默认 `http://127.0.0.1:3081`）；
4. harness-bridge 读取 `GET /api/v1/internal/dify/apps`（服务令牌），按注册表**关键字**路由（不做本地模型兜底）：
    - 用户原话包含某应用关键字（逗号/顿号分隔；关键字为空时回退意图描述）→ 用该应用的 API Key 调用 Dify；
    - 类型为 Agent：`POST /v1/chat-messages`（仅 `response_mode=streaming`，聚合 SSE `agent_message`/`message`）；
    - 类型为 Workflow：`POST /v1/workflows/run`（blocking），输入字段 `query`；
    - 多个关键字同时命中时，取更长的关键字；
    - 未配置 API Key：不请求 Dify，返回未配置说明；
    - **无关键字命中：直接调用大模型文本回答**（默认 GLM `glm-4.7-flash`；可用环境变量 `DEEPSEEK_API_KEY` / `GLM_API_KEY` / `GLM_MODEL` / `PLATFORM2_LLM_*` 覆盖；密钥亦可来自 `.dsh-home/.credentials.yaml` 的 `refs`）；
5. bridge 输出标准化 SSE：`thinking / tool_call / tool_result / answer`；可附带 `business_payload`；
6. 前端渲染文本与工具调用；监听 `business_payload` 驱动 Cesium / 任务窗口。

#### 2.3.2 `dsh web` 对话
1. 用户在 `dsh web`（:3080）输入自然语言；
2. 提问前调用 MCP `route_dify_message`，规则与 2.3.1 关键字/类型/API Key 一致；
3. 命中则返回 Dify 结果；未命中则由 dsh 默认模型（与 bridge 对齐：GLM `glm-4.7-flash`）直接回答。

### 2.4 双交互模式
- 界面交互：表单、按钮、时间轴操作，直接调用后端REST业务接口；
- AI对话交互：自然语言指令，关键字路由 + Dify / 大模型，调用同一套后端业务接口；
两套入口复用相同业务逻辑，页面表现一致。

## 3. 功能需求
### 3.1 Cesium三维地球模块
1. 基础三维地球：平移、缩放、旋转相机；
2. 飞机点位标绘：自定义点位符号、颜色区分；实时点位动态渲染；
3. 航迹标绘：绘制合批航迹线；图层开关：点位图层、航迹图层；
4. 查询模式状态控制：标记查询模式，控制实时点位流启停。

### 3.2 态势查询模块
1. 查询表单：时间范围、飞机编号等筛选条件；
2. 支持实时态势查询、历史态势回溯查询；
3. 查询结果点位标绘；查询模式下暂停实时点位；
4. 一键清空地图标绘。

### 3.3 图像检测任务模块
1. 支持多路任务并发接收图片；
2. 对接外部图像检测算法服务，接收单图飞机检测点；
3. 后端检测点合批逻辑，生成航迹；
4. 时间轴组件（vis-timeline）：按图片接收时间成帧；点击/拖动播放头吸附到最近帧，切换航迹与图片；
5. 任务列表悬浮工具窗口：展示任务清单、任务状态，选中任务查看航迹图像；
6. 一期图像推送与检测点允许种子造数，不强制对接外部检测服务。

### 3.4 AI对话模块
1. 对话面板：输入框、对话历史记录；支持清空对话；
2. 推理面板：流式展示思考内容、工具调用、工具返回结果，支持折叠展开；
3. 终止任务：可停止正在执行的AI推理任务；
4. SSE流式输出，事件类型：`thinking`、`tool_call`、`tool_result`、`answer`；
5. SSE事件支持附加`business_payload`，携带态势点位、任务列表结构化数据；
6. 平台对话依赖 harness-bridge（:3081）在线；`scripts/start-ai-stack.sh` 启动该服务。

### 3.5 Dify垂域应用管理（管理员）
1. 页面路由 `/admin/dify`。态势主页工具栏提供「Dify管理」入口。需管理员 JWT，操作员调用接口返回 403。
2. 注册表 CRUD：新增、编辑、启用/禁用、删除。
3. 录入字段：
    - 应用名称
    - Dify AppID（创建后不可改）
    - 类型：Agent 或 Workflow
    - 意图描述
    - 关键字：逗号分隔，供 bridge / `dsh` 匹配
    - API Key：Dify 应用密钥 `app-...`；编辑时留空表示不修改
    - 启用状态
4. 仅启用且已填写 API Key 的记录会被真正调用。

### 3.6 用户与权限
1. 账号密码登录，JWT鉴权；默认 `operator/operator`、`admin/admin`；
2. 角色：操作员、管理员；管理员可进 `/admin/*`；
3. 会话、对话消息、工具调用日志持久化。

## 4. 页面/组件结构
1. **登录页面**：账号密码登录
2. **三维态势主页面（核心页面）**
    - Cesium三维地球（主区域）
    - 侧边：态势查询折叠表单
    - 底部：时间轴组件
    - 右侧：AI对话面板（可折叠）
    - 悬浮弹窗：任务列表工具窗口（默认隐藏，按钮/对话指令唤起）
    - 顶部工具栏：切换实时/查询模式、图层开关、清空标绘、Dify管理/日志入口
3. **Dify垂域应用管理页面（管理员，`/admin/dify`）**：登记 Agent 或 Workflow 的 AppID、关键字、API Key，并维护启用状态
4. **日志页面（管理员）**：对话日志、工具调用日志查看

## 5. 技术架构
### 5.1 整体架构
```
Vue3 前端（对话面板）
  ↓ SSE JWT
FastAPI :8000
  GET /api/v1/ai/chat/stream
  ↓ GET /v1/chat/stream
harness-bridge :3081          ← 平台对话专用（scripts/start-ai-stack.sh）
  ├─ 关键字命中 → Dify :5001（Agent streaming / Workflow blocking）
  └─ 未命中     → 大模型（默认 GLM glm-4.7-flash；可配 DeepSeek）
                 无本地模型兜底

dsh web :3080                 ← 真 Harness（scripts/dsh web）
  └─ MCP platform2-dify（scripts/dify-mcp）
       读 FastAPI GET /api/v1/internal/dify/apps
       关键字规则同上 → Dify 或 dsh 默认大模型

Dify 官方 Compose :5001
FastAPI 业务：鉴权、/admin/dify、/situation、internal 服务令牌接口
```

外部依赖
├─ 实时飞机点位推送源（一期可用种子造数模拟）
└─ 图像检测算法服务（一期用造数：任务图片、检测点、合批航迹；可不接真实检测服务）

### 5.2 前端技术栈
- Vue3 + Vite + PNPM
- CesiumJS：三维渲染、点位/航迹标绘
- Pinia：独立Store：`useSituationStore`、`useTaskTrackStore`、`useAiChatStore`
- Element Plus：表单、弹窗、抽屉等交互组件（Vue3 版 Element UI）
- vis-timeline：任务图像时间轴（交互参考 `VueProject/2026/platform` 的 VisMissionTimeline；不按连续时间 scrub，按帧吸附）
- Fetch：REST请求 + SSE流式对话

### 5.3 后端与 AI 侧技术栈
- FastAPI + Uvicorn；SQLAlchemy 2.0 + Alembic；PostgreSQL
- httpx：调用 harness-bridge、Dify、图像检测服务
- harness-bridge（FastAPI）：平台 SSE 适配、关键字路由、大模型调用
- DeepSeek Harness：`deepseek-harness/` + `.dsh-home`；MCP stdio `scripts/dify-mcp`
- Dify 1.17.1：`dify/docker`，宿主端口 5001

### 5.4 数据库表设计
**基础表（平台底座）**
1. `users` 用户表
2. `dify_agent_registry` Dify垂域注册表：`app_id`、`name`、`app_type`（agent/workflow）、`intent_desc`、`keywords`、`api_key`、`enabled`
3. `ai_chat_session` AI对话会话表
4. `ai_chat_message` AI对话消息表
5. `ai_tool_call` AI工具调用日志表

**业务表（sit_前缀，态势业务）**
1. `sit_aircraft_point` 飞机历史态势点位
2. `sit_task_info` 任务主信息
3. `sit_task_image` 任务图片元数据（图片接收时间，关联task_id）
4. `sit_image_detection_result` 单图检测点
5. `sit_track` 合批航迹表

## 6. 迁移能力设计
1. **前端模块目录隔离**
    `src/modules/` 下划分：`cesiumRender`、`situation`、`taskTrack`、`aiChat`，模块之间通过接口通信，低耦合；可单独复制迁移到其他Vue项目。
2. **后端路由分组隔离**
    - AI相关接口：`/api/v1/ai`
    - Dify管理：`/api/v1/admin/dify`
    - 态势业务：`/api/v1/situation`
    代码包独立划分，可以单独迁移。
3. **数据库分层**：基础表与业务表命名区分，迁移脚本独立，可以选择性导入。
4. **AI配置可导出**：Dify工作流配置、dsh profile / credentials、注册表关键字可导出，迁移环境直接导入。
5. **SSE事件结构标准化**，业务payload为可选扩展字段，不破坏基础对话消息结构。

## 7. 非功能需求
1. 模块化可移植：模块内聚，依赖清晰，支持整体/分模块迁移；
2. Cesium渲染性能：大量点位、航迹做渲染优化，避免页面卡顿；
3. AI对话超时：单次推理最大120s（Agent streaming / 大模型）；
4. 并发：支持多路任务同时推送图片；
5. 数据持久化：态势、任务、图片元信息、对话日志持久化；
6. 可扩展：新增垂域能力时，在 Dify 创建 Agent 或 Workflow，再于 `/admin/dify` 录入关键字与 API Key；平台对话与 `dsh` 新会话即可按关键字调用。新增航迹类型、查询条件仍扩展业务模块。

## 8. 异常场景
1. 实时点位流中断：前端提示，停止点位更新，不影响三维球、对话功能；
2. 图像检测算法服务异常：图片检测失败，前端提示，不阻断其他任务；
3. Dify服务不可用 / 未配 API Key：返回文本提示，无法执行垂域业务查询；
4. harness-bridge 不可达或返回非 2xx：FastAPI SSE 提示「Harness 返回 …」或连接失败；确认 `PLATFORM2_HARNESS_BASE_URL` 指向 `:3081` 而非 `dsh` 的 `:3080`；
5. 大模型密钥缺失、余额不足或上游限流（如 429）：未命中关键字时返回明确错误文案，**不回退本地模型**；
6. SSE业务payload解析异常：捕获异常，不破坏对话流。

## 9. 接口清单
### 9.1 AI对话接口 `/api/v1/ai`
1. `GET /api/v1/ai/chat/stream` SSE流式对话（转发 harness-bridge :3081）
2. `POST /api/v1/ai/chat/session` 创建对话会话
3. `DELETE /api/v1/ai/chat/session/{id}` 删除会话

### 9.2 Dify垂域管理 `/api/v1/admin/dify`（仅管理员）
1. `GET /api/v1/admin/dify` 列表
2. `POST /api/v1/admin/dify` 新增（`app_id` 重复则 400）
3. `PUT /api/v1/admin/dify/{app_id}` 更新名称、类型、意图、关键字、API Key、启用状态；API Key 空字符串不覆盖
4. `DELETE /api/v1/admin/dify/{app_id}` 删除
5. `GET /api/v1/internal/dify/apps` 供 MCP / bridge 读取（含 API Key；`Authorization: Bearer <service_token>`，不接受用户 JWT）

### 9.3 态势业务接口 `/api/v1/situation`
1. `GET /api/v1/situation/aircraft/realtime` 实时飞机点位推送接收
2. `POST /api/v1/situation/aircraft/query` 态势查询（实时/回溯）
3. `GET /api/v1/situation/task/list` 获取任务列表
4. `POST /api/v1/situation/task` 创建任务
5. `POST /api/v1/situation/task/image` 接收任务图片
6. `POST /api/v1/situation/task/image/detection` 上报图片检测结果
7. `GET /api/v1/situation/task/{task_id}/timeline` 获取任务时间轴元数据
8. `GET /api/v1/situation/task/{task_id}/track` 获取任务航迹数据

### 9.4 用户登录 `/api/v1/auth`
1. `POST /api/v1/auth/login` 用户登录，返回JWT

### 9.5 本地进程端口约定
| 服务 | 端口 | 说明 |
|------|------|------|
| FastAPI | 8000 | 平台后端 |
| harness-bridge | 3081 | 平台对话 SSE |
| dsh web | 3080 | 真 Harness UI |
| Dify Nginx | 5001 | 官方 Compose |

## 10. SSE事件定义（harness-bridge / 平台消费）
```json
// thinking
{
  "event_type": "thinking",
  "content": "正在连接智能体…",
  "session_id": "…"
}
// tool_call
{
  "event_type": "tool_call",
  "tool_name": "call_dify_app",
  "params": {"dify_app_id": "situation-query", "query": "查询实时态势"}
}
// tool_result
{
  "event_type": "tool_result",
  "content": "Dify 返回结果",
  "business_payload": {
    "type": "aircraft_situation",
    "data": {"points": [...]}
  }
}
// answer（命中 Dify 或大模型闲聊）
{
  "event_type": "answer",
  "content": "已查询到实时态势信息，三维球已标绘飞机点位。",
  "provider": "dify",
  "business_payload": {
    "type": "aircraft_situation",
    "data": {"points": [...]}
  }
}
```

## 11. 修订记录
| 版本 | 日期 | 说明 |
|------|------|------|
| V1.5 | 2026-10-16 | 明确平台对话走 harness-bridge :3081；关键字路由；未命中调大模型（默认 GLM glm-4.7-flash）；无本地模型兜底；Agent 仅 streaming |
| V1.4 | 2026-10-16 | `/admin/dify` 关键字与 API Key；`route_dify_message` 按类型调 Dify |
| V1.3 | 2026-10-16 | 独立完整项目骨架与双业务主线 |
