/**
 * 作业流行为目录（前端唯一真相）。
 * Skill / harness-bridge 默认 next_actions 须与此保持一致。
 */

/** @typedef {{ id: string, label: string, utterance: string }} ActionChip */

/** @typedef {{
 *   id: string,
 *   label: string,
 *   utterance: string,
 *   type: string,
 *   tool: string,
 *   next: string[],
 *   doneWhen: (s: object) => boolean,
 * }} CatalogAction */

/** @type {CatalogAction[]} */
export const ACTION_CATALOG = [
  {
    id: 'list_tasks',
    label: '查询任务',
    utterance: '查询当前检测任务',
    type: 'task_list',
    tool: 'internal_list_detection_tasks',
    next: ['open_task'],
    doneWhen: (s) => (s.tasks?.length || 0) > 0,
  },
  {
    id: 'open_task',
    label: '打开任务',
    utterance: '打开任务',
    type: 'task_open',
    tool: 'internal_open_detection_task',
    next: ['load_points', 'load_tracks'],
    doneWhen: (s) => Boolean(s.selectedTaskId),
  },
  {
    id: 'load_points',
    label: '加载检测点',
    utterance: '加载检测点',
    type: 'detection_points',
    tool: 'internal_get_task_detection_points',
    next: ['load_tracks', 'load_images', 'load_associated'],
    doneWhen: (s) => (s.detectionPoints?.length || 0) > 0,
  },
  {
    id: 'load_tracks',
    label: '加载检测航迹',
    utterance: '加载检测航迹',
    type: 'detection_tracks',
    tool: 'internal_get_task_detection_tracks',
    next: ['load_images', 'load_associated'],
    doneWhen: (s) => (s.detectionTracks?.length || 0) > 0,
  },
  {
    id: 'load_images',
    label: '加载检测图像',
    utterance: '加载检测图像',
    type: 'detection_images',
    tool: 'internal_get_task_detection_images',
    next: ['load_associated', 'load_points'],
    doneWhen: (s) => (s.images?.length || 0) > 0,
  },
  {
    id: 'load_associated',
    label: '加载时空关联态势点',
    utterance: '加载时空关联态势点',
    type: 'associated_situation',
    tool: 'internal_get_task_associated_situation',
    next: ['load_tracks', 'load_images'],
    doneWhen: (s) => (s.associatedPoints?.length || 0) > 0,
  },
]

const byId = Object.fromEntries(ACTION_CATALOG.map((a) => [a.id, a]))
const byType = Object.fromEntries(ACTION_CATALOG.map((a) => [a.type, a]))

/** type 别名（历史兼容） */
byType.aircraft_situation = byType.associated_situation

export function getActionById(id) {
  return byId[id] || null
}

export function getActionByType(type) {
  return byType[type] || null
}

export function knownTypes() {
  return ACTION_CATALOG.map((a) => a.type)
}

/** 从 store 快照收集已完成行为 id */
export function collectDoneIds(snapshot) {
  return ACTION_CATALOG.filter((a) => a.doneWhen(snapshot)).map((a) => a.id)
}

/** @returns {ActionChip[]} */
export function chipsForIds(ids, { excludeDone = [] } = {}) {
  const done = new Set(excludeDone)
  return (ids || [])
    .map((id) => byId[id])
    .filter((a) => a && !done.has(a.id))
    .map((a) => ({ id: a.id, label: a.label, utterance: a.utterance }))
}

/** 按当前 type 给出默认下一步（可按 done 过滤） */
export function defaultNextActions(type, doneIds = []) {
  const action = getActionByType(type)
  if (!action) return []
  return chipsForIds(action.next, { excludeDone: doneIds })
}

/** 规范化智能体返回的 next_actions，并过滤已完成 / 非目录项 */
export function normalizeNextActions(payload, doneIds = []) {
  const done = new Set(doneIds)
  const fromPayload = Array.isArray(payload?.next_actions) ? payload.next_actions : []
  const cleaned = fromPayload
    .map((a) => {
      if (!a) return null
      const byUtterance = ACTION_CATALOG.find((c) => c.utterance === a.utterance || c.id === a.id)
      const id = a.id || byUtterance?.id || a.utterance
      const catalog = byId[id] || byUtterance
      if (!catalog) return null
      if (done.has(catalog.id)) return null
      return {
        id: catalog.id,
        label: a.label || catalog.label,
        utterance: a.utterance || catalog.utterance,
      }
    })
    .filter(Boolean)

  if (cleaned.length) return cleaned
  return defaultNextActions(payload?.type, doneIds)
}

/** 供对话 context 拼接：done=id1,id2 */
export function formatDoneContext(doneIds) {
  if (!doneIds?.length) return ''
  return `done=${doneIds.join(',')}`
}
