import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/api/http'

export const useTaskTrackStore = defineStore('taskTrack', () => {
  const tasks = ref([])
  const selectedTaskId = ref(null)
  const opened = ref(null)
  const frames = ref([])
  const images = ref([])
  const currentFrame = ref(0)
  const detectionPoints = ref([])
  const detectionTracks = ref([])
  const associatedPoints = ref([])
  const panelOpen = ref(false)

  const selectedTask = computed(() =>
    tasks.value.find((t) => t.id === selectedTaskId.value) || opened.value?.task || null,
  )

  function clearLayers() {
    frames.value = []
    images.value = []
    currentFrame.value = 0
    detectionPoints.value = []
    detectionTracks.value = []
    associatedPoints.value = []
  }

  async function loadTasks() {
    const data = await api('/api/v1/situation/task/list')
    tasks.value = data.tasks || []
    return tasks.value
  }

  async function queryTasks() {
    panelOpen.value = true
    return loadTasks()
  }

  async function openTask(taskId) {
    selectedTaskId.value = taskId
    panelOpen.value = true
    clearLayers()
    const data = await api(`/api/v1/situation/task/${encodeURIComponent(taskId)}`)
    opened.value = data
    return data
  }

  async function loadDetectionPoints() {
    if (!selectedTaskId.value) return null
    const data = await api(
      `/api/v1/situation/task/${encodeURIComponent(selectedTaskId.value)}/detections`,
    )
    detectionPoints.value = data.points || []
    return data
  }

  async function loadDetectionTracks() {
    if (!selectedTaskId.value) return null
    const data = await api(
      `/api/v1/situation/task/${encodeURIComponent(selectedTaskId.value)}/tracks`,
    )
    detectionTracks.value = data.tracks || []
    return data
  }

  async function loadImages() {
    if (!selectedTaskId.value) return null
    const data = await api(
      `/api/v1/situation/task/${encodeURIComponent(selectedTaskId.value)}/images`,
    )
    images.value = data.images || []
    frames.value = data.frames || []
    currentFrame.value = 0
    return data
  }

  async function loadAssociatedSituation() {
    if (!selectedTaskId.value) return null
    const data = await api(
      `/api/v1/situation/task/${encodeURIComponent(selectedTaskId.value)}/associated-situation`,
    )
    associatedPoints.value = data.points || []
    return data
  }

  function setCurrentFrame(index) {
    if (!frames.value.length) {
      currentFrame.value = 0
      return
    }
    currentFrame.value = Math.max(0, Math.min(frames.value.length - 1, index))
  }

  /** 对话 hydrate：与 loadXxx 写同一批字段 */
  function hydrateTaskList(data) {
    panelOpen.value = true
    tasks.value = data.tasks || []
  }

  function hydrateOpened(data) {
    const task = data.task
    if (!task?.id) return
    selectedTaskId.value = task.id
    opened.value = data
    clearLayers()
    if (!tasks.value.some((t) => t.id === task.id)) {
      tasks.value = [task, ...tasks.value]
    }
    panelOpen.value = true
  }

  function hydrateDetectionPoints(data) {
    if (data.task_id) selectedTaskId.value = data.task_id
    detectionPoints.value = data.points || []
  }

  function hydrateDetectionTracks(data) {
    if (data.task_id) selectedTaskId.value = data.task_id
    detectionTracks.value = data.tracks || []
  }

  function hydrateDetectionImages(data) {
    if (data.task_id) selectedTaskId.value = data.task_id
    images.value = data.images || []
    frames.value = data.frames || []
    currentFrame.value = 0
  }

  function hydrateAssociated(data) {
    if (data.task_id) selectedTaskId.value = data.task_id
    associatedPoints.value = data.points || []
  }

  /** 供 actionCatalog.collectDoneIds 使用 */
  function workflowSnapshot() {
    return {
      tasks: tasks.value,
      selectedTaskId: selectedTaskId.value,
      detectionPoints: detectionPoints.value,
      detectionTracks: detectionTracks.value,
      images: images.value,
      associatedPoints: associatedPoints.value,
    }
  }

  return {
    tasks,
    selectedTaskId,
    selectedTask,
    opened,
    frames,
    images,
    currentFrame,
    detectionPoints,
    detectionTracks,
    associatedPoints,
    panelOpen,
    clearLayers,
    loadTasks,
    queryTasks,
    openTask,
    loadDetectionPoints,
    loadDetectionTracks,
    loadImages,
    loadAssociatedSituation,
    setCurrentFrame,
    hydrateTaskList,
    hydrateOpened,
    hydrateDetectionPoints,
    hydrateDetectionTracks,
    hydrateDetectionImages,
    hydrateAssociated,
    workflowSnapshot,
  }
})
