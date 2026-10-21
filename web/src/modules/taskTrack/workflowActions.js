import { getActionByType, normalizeNextActions } from './actionCatalog'

/**
 * 将对话 business_payload 应用到领域 store（与按钮共用同一写路径）。
 * @returns {{ nextActions: Array<{id:string,label:string,utterance:string}> } | null}
 */
export function applyBusinessPayload(payload, { taskTrack, enterTaskMode, doneIds = [] } = {}) {
  if (!payload?.type) return null
  const type = payload.type === 'aircraft_situation' ? 'associated_situation' : payload.type
  if (!getActionByType(type)) {
    console.warn('[workflowActions] unknown type, ignored:', payload.type)
    return null
  }

  const data = payload.data || {}

  if (type === 'task_list') {
    taskTrack.hydrateTaskList(data)
  } else if (type === 'task_open') {
    if (!data.task?.id) return null
    enterTaskMode?.()
    taskTrack.hydrateOpened(data)
  } else {
    if (data.task_id) taskTrack.selectedTaskId = data.task_id
    enterTaskMode?.()
    if (type === 'detection_points') taskTrack.hydrateDetectionPoints(data)
    else if (type === 'detection_tracks') taskTrack.hydrateDetectionTracks(data)
    else if (type === 'detection_images') taskTrack.hydrateDetectionImages(data)
    else if (type === 'associated_situation') taskTrack.hydrateAssociated(data)
  }

  const resolvedDone = typeof doneIds === 'function' ? doneIds() : doneIds
  const nextActions = normalizeNextActions({ ...payload, type }, resolvedDone || [])
  return { nextActions }
}
