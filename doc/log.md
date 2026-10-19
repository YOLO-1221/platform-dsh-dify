# platform2 开发记录

## 2026-10-16
- 前端 UI 组件库由 Naive UI 替换为 Element Plus（Element UI / Vue3）。
- PRD 升至 V1.5：双入口（bridge :3081 / dsh :3080）、关键字路由、未命中走大模型（默认 GLM `glm-4.7-flash`）、无本地模型兜底、Agent streaming。
- 平台对话改打 harness-bridge `:3081`（真 dsh 占 `:3080`），消除 Harness 404；bridge 按注册表关键字/API Key 调 Dify。
- Dify 注册页强制关键字与 API Key，并展示从 Dify 取 Key 的步骤；HTTP 错误展示 detail 正文。
- 前端记住登录角色；`/admin/*` 仅 admin 可进；登录页提示用 admin/admin 注册 Dify。
- `LLM_BUILD_PROMPT.md` 与 PRD V1.4 对齐；Dify 管理页补充缺 Key 提示与控制台入口。
- PRD 升至 V1.4：写明 `/admin/dify` 登记关键字与 API Key，以及 `dsh` 经 `route_dify_message` 按类型调用 Dify。
- Dify 注册表增加关键字与 API Key。`scripts/dify-mcp` 供 dsh 在提问前按关键字调用已登记的 Agent 或 Workflow。
- 用 Docker Desktop 部署官方 Dify 1.17.1（`dify/docker`，宿主端口 5001）。`scripts/start-dify.sh` 启动；AI 栈默认不再抢占该端口。
- 将 DeepSeek Harness 迁入本仓库 `deepseek-harness/`；`scripts/dsh` + `~/.local/bin/dsh` 指向该树，默认 `DSH_HOME=.dsh-home`。
- 旧路径 `VueProject/2026/deepseek-harness` 保留为软链；AOCI 排除 `deepseek-harness` / `.dsh-home`。
- 补齐 Dify 垂域注册表 CRUD：`PUT/DELETE /api/v1/admin/dify/{app_id}`，管理页支持编辑、启用开关、删除。
- 态势主页工具栏增加 Dify 管理 / 日志入口。
