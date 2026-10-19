import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/api/http'

export const useTaskTrackStore = defineStore('taskTrack', () => {
  const tasks = ref([])
  const selectedTaskId = ref(null)
  const frames = ref([])
  const currentFrame = ref(0)
  const track = ref(null)
  const panelOpen = ref(false)

  const selectedTask = computed(() =>
    tasks.value.find((t) => t.id === selectedTaskId.value) || null,
  )

  async function loadTasks() {
    const data = await api('/api/v1/situation/task/list')
    tasks.value = data.tasks || []
    return tasks.value
  }

  async function selectTask(taskId) {
    selectedTaskId.value = taskId
    panelOpen.value = true
    const [timeline, trackData] = await Promise.all([
      api(`/api/v1/situation/task/${taskId}/timeline`),
      api(`/api/v1/situation/task/${taskId}/track`),
    ])
    frames.value = timeline.frames || []
    currentFrame.value = 0
    track.value = trackData
    return { timeline, trackData }
  }

  function setCurrentFrame(index) {
    if (!frames.value.length) {
      currentFrame.value = 0
      return
    }
    currentFrame.value = Math.max(0, Math.min(frames.value.length - 1, index))
  }

  return {
    tasks,
    selectedTaskId,
    selectedTask,
    frames,
    currentFrame,
    track,
    panelOpen,
    loadTasks,
    selectTask,
    setCurrentFrame,
  }
})
