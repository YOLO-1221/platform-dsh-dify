import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/http'

export const useSituationStore = defineStore('situation', () => {
  const mode = ref('realtime') // realtime | query
  const points = ref([])
  const layers = ref({ points: true, tracks: true })
  let realtimeTimer = null

  async function fetchRealtime() {
    const data = await api('/api/v1/situation/aircraft/realtime')
    points.value = data.points || []
  }

  async function query(payload) {
    const data = await api('/api/v1/situation/aircraft/query', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    mode.value = 'query'
    stopRealtime()
    points.value = data.points || []
    return data
  }

  function startRealtime() {
    mode.value = 'realtime'
    stopRealtime()
    fetchRealtime().catch(() => {})
    realtimeTimer = setInterval(() => {
      fetchRealtime().catch(() => {})
    }, 5000)
  }

  function stopRealtime() {
    if (realtimeTimer) {
      clearInterval(realtimeTimer)
      realtimeTimer = null
    }
  }

  function resumeRealtime() {
    startRealtime()
  }

  function clearPlot() {
    points.value = []
  }

  return {
    mode,
    points,
    layers,
    query,
    startRealtime,
    stopRealtime,
    resumeRealtime,
    clearPlot,
  }
})
