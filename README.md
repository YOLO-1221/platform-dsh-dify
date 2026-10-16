# platform2｜三维空域态势智能平台

独立完整项目骨架：Vue3 + Cesium + vis-timeline 前端，FastAPI 后端，默认 PostgreSQL。一期图像/检测点/航迹用造数。平台对话 SSE 走 harness-bridge（:3081）；真 `dsh web` 占 :3080。Dify 官方栈在 :5001。注册表关键字命中后调用对应 Agent/Workflow。

## 启动

```bash
# 后端
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# 需本机 PostgreSQL 16，库 platform2，用户 platform2
uvicorn app.main:app --reload --port 8000

# 前端（另开终端）
cd web
pnpm install
pnpm dev
```

默认账号：`operator/operator`，`admin/admin`。

```bash
# AI 栈（另开终端；依赖上面的后端）
chmod +x scripts/start-ai-stack.sh
./scripts/start-ai-stack.sh
# 关键字命中 → Dify；未命中 → 大模型回复（默认与 dsh 一致：GLM glm-4.7-flash）
# 密钥：DEEPSEEK_API_KEY 或 GLM_API_KEY（环境变量，或 .dsh-home/.credentials.yaml refs）
# 可覆盖：GLM_MODEL / PLATFORM2_LLM_MODEL
```

### DeepSeek Harness（`dsh`）

源码在本仓库 `deepseek-harness/`（旧路径 `VueProject/2026/deepseek-harness` 为指向此处的软链）。

```bash
# 包装脚本默认 DSH_HOME=<repo>/.dsh-home，并调用 vendored 树里的 pnpm dsh
./scripts/dsh web          # Web UI / agent :3080（真 Harness）
# 或：PATH 已含 ~/.local/bin 时
dsh web
```

首次从源码跑需在 `deepseek-harness/` 内已完成 `pnpm install` 与 `pnpm run build`。平台前端对话走 `:3081` 的 harness-bridge（`./scripts/start-ai-stack.sh`），不要与 `dsh web` 抢 `:3080`。

### Dify（官方 Compose）

源码在 `dify/`（1.17.1）。需 Docker Desktop 已运行。Nginx 映射到宿主 **5001**，与 harness-bridge 的 `PLATFORM2_DIFY_BASE` 对齐。

```bash
chmod +x scripts/start-dify.sh
./scripts/start-dify.sh
# 浏览器打开 http://127.0.0.1:5001/install 创建管理员
```

`scripts/start-ai-stack.sh` 默认不再占用 5001。只有停掉官方 Dify 后，才用 `PLATFORM2_START_DIFY_LOCAL=1` 启动进程内兼容桩。

在管理页 `/admin/dify` 填写关键字和 API Key 后，重新打开一次 `dsh` 会话。提问前 `dsh` 会调用 `route_dify_message`：命中关键字则请求对应 Dify Agent（`/v1/chat-messages`）或 Workflow（`/v1/workflows/run`）。

## 目录

- `web/src/modules/`：`cesiumRender`、`situation`、`taskTrack`、`aiChat`
- `server/app/api/v1/`：`auth`、`ai`、`admin/dify`、`situation`
- `deepseek-harness/`：DeepSeek Harness 源码与 `dsh` CLI
- `dify/`：官方 Dify 1.17.1（`docker compose`，控制台 `:5001`）
- `.dsh-home/`：本仓库 `dsh` 运行态（profiles / credentials，不入库）
- `doc/PRD.md`、`doc/LLM_BUILD_PROMPT.md`
# platform-dsh-dify
