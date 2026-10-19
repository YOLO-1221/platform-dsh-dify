# AOCI 维护与自动更新

本仓库使用 Volumes v1（`aoci.txt` + `aoci.code.txt` + `aoci.database.txt` + `aoci.meta.txt`）。认知语义由 **Host 模型** 基于源码证据撰写；AOCI 只签发候选、校验并原子写入。

## 对话后自动更新（已开启）

目标：你在 Cursor 里和 Agent **对话改完代码后**，尽量自动把 AOCI 收尾做完。

机制（两段钩子）：

1. **`afterFileEdit`** → `.cursor/hooks/aoci-mark-dirty.sh`  
   改了业务文件就在 `.run/aoci-dirty` 打标记（忽略 `aoci*.txt`、`.aoci/`、`.run/`）。

2. **`stop`（每轮对话结束）** → `.cursor/hooks/aoci-stop-remind.sh`  
   - `aoci verify` 发现漂移，或本轮有 dirty 标记 → 自动注入 `followup_message`  
   - Agent 被要求立刻跑 `aoci_maintain` → `aoci_update_entry` 直到对齐  
   - 已对齐 → 清 dirty，不再打断  
   - `loop_limit: 2`，避免死循环  

配置：`.cursor/hooks.json`。首次启用或改钩子后，在 Cursor **Hooks** 面板确认已加载，必要时重开窗口。

限制：钩子**不能**替模型写 F/R/A/S，只能**自动再开一轮**让 Agent 用 MCP 写完。纯问答、零改文件 → 不会更新。

## 日常收尾步骤（Agent 执行）

1. `aoci_maintain`（MCP；省略 scope）
2. 有 `candidates`：读源码 → `aoci_update_entry`（整批，`code_batch_id` = `code_plan.batch_id`）
3. `remaining > 0` 继续 maintain，直到归零
4. `aoci verify` → `aoci check` → `aoci index agent guide --agent cursor`

中间改一半时不要反复 Maintain。合同见 `AGENTS.md`。

## 为什么不能后台脚本直接改文档

| 层级 | 无人值守 |
|------|----------|
| 漂移检测 | 可以 |
| Baseline / CAS 写入 | 可以 |
| Tag / F/R/A/S | **必须**模型读证据创作 |

「自动更新」= 对话结束后自动驱动 Agent 走 Maintain→Update，不是静默改 `aoci.code.txt`。

## 可选：AOCI AI 增强

`.aoci/config.json` 默认 `"ai.enabled": false`。开启后可批量起草草稿，仍须校验 Apply；Volumes 正式写入仍以 MCP 为准。

## 禁止事项

1. 禁止手改 `aoci.code.txt` 等 Volume 正文（会 `code_volume_unbaselined`，Maintain 卡死）。
2. 不要用对 Volumes 只读的旧 CLI：`aoci index update` / `index agent plan`。
3. 不要改 Baseline 哈希「接受」漂移。

## 诊断

```bash
export PATH="$HOME/.local/bin:$PATH"
aoci verify --repo . --json
aoci check --repo . --json
aoci index agent guide --agent cursor --json
aoci doctor --repo .
```
