---
name: situation-workflow
description: 匹配作业流行为，调用态势工具，原样输出 business_payload，并按 done 推荐下一步。
---

# 态势作业流（行为 + 下一步）

每次只做一步：匹配用户意图 → 调用对应工具 → 用固定 JSON 回复。  
`data` 必须等于工具返回体；`next_actions` 只推荐尚未完成的下一步，不要一次执行多步。

前端行为目录（唯一真相，`web/src/modules/taskTrack/actionCatalog.js`）与下表一致。

## 1. 上下文

若用户消息末尾有：

```text
[context] task_id=...; done=list_tasks,open_task,load_points
```

则：

- 后续步骤优先用该 `task_id`
- `next_actions` **不得**包含 `done` 里已有的 id
- 没有 `task_id` 且需要任务相关步骤时：先查任务列表；只有一个任务就用它，有多个就先让用户选择（`type=task_list`）

## 2. 行为匹配

| 用户说法 / utterance | id | 工具 | type |
|---|---|---|---|
| 查询任务、检测任务、查询当前检测任务 | list_tasks | internal_list_detection_tasks | task_list |
| 打开任务 | open_task | internal_open_detection_task | task_open |
| 加载检测点 | load_points | internal_get_task_detection_points | detection_points |
| 加载检测航迹 | load_tracks | internal_get_task_detection_tracks | detection_tracks |
| 加载检测图像 | load_images | internal_get_task_detection_images | detection_images |
| 加载时空关联态势点 | load_associated | internal_get_task_associated_situation | associated_situation |

只允许上表内的 `type` / `id` / `utterance`。

## 3. 输出契约（只输出这段 JSON）

可包在 ```json 代码块中，不要再写其它说明文字。

```json
{
  "answer": "已加载检测点 16 条。建议下一步加载检测航迹。",
  "business_payload": {
    "type": "detection_points",
    "data": {},
    "next_actions": [
      {
        "id": "load_tracks",
        "label": "加载检测航迹",
        "utterance": "加载检测航迹"
      },
      {
        "id": "load_images",
        "label": "加载检测图像",
        "utterance": "加载检测图像"
      }
    ]
  }
}
```

字段约定：

- `type`：当前已完成的行为（上表之一）
- `data`：工具返回体原样（禁止改写坐标/列表）
- `next_actions`：数组；每项必须有 `id`、`label`、`utterance`
  - `utterance`：用户一点就发给对话的原话，前端会原样发送
  - 最多 3 条；不要推荐 `done` 已包含或当前刚完成的步骤

## 4. 推荐下一步（固定表，再减 done）

| 当前 type | 默认 next id（按序） |
|---|---|
| task_list | open_task |
| task_open | load_points；load_tracks |
| detection_points | load_tracks；load_images；load_associated |
| detection_tracks | load_images；load_associated |
| detection_images | load_associated；load_points |
| associated_situation | load_tracks；load_images |

`utterance` 固定用目录中的原文（见上表）。

## 5. 失败

工具失败时不要输出假 `business_payload`。用自然语言说明原因；可给空的 `next_actions` 或不输出 JSON。
