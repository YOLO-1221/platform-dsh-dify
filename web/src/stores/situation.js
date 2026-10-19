import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/http'

/** 本地墙钟时间，不带 Z，与库内 naive datetime / 日期选择器一致 */
function toApiDateTime(date) {
  if (!date) return undefined
  const d = date instanceof Date ? date : new Date(date)
  if (Number.isNaN(d.getTime())) return undefined
  const pad = (n) => String(n).padStart(2, '0')
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  )
}

function buildTimeBody(payload) {
  return {
    aircraft_id: payload.aircraft_id || undefined,
    start_time: toApiDateTime(payload.start_time),
    end_time: toApiDateTime(payload.end_time),
  }
}

/** 同一飞机只保留 observed_at 最新的一点 */
function latestPointPerAircraft(points) {
  const map = new Map()
  for (const p of points || []) {
    const prev = map.get(p.aircraft_id)
    if (!prev || String(p.observed_at) > String(prev.observed_at)) {
      map.set(p.aircraft_id, p)
    }
  }
  return [...map.values()]
}

export const useSituationStore = defineStore('situation', () => {
  const mode = ref('realtime') // realtime | query
  const points = ref([])
  const tracks = ref([])
  const lastQuery = ref(null)
  const lastResult = ref({ pointCount: 0, trackCount: 0, truncated: false })
  const layers = ref({ points: true, tracks: true })
  let realtimeTimer = null

  async function fetchRealtime() {
    const data = await api('/api/v1/situation/aircraft/realtime')
    points.value = data.points || []
  }

  function enterQueryMode() {
    mode.value = 'query'
    stopRealtime()
  }

  /**
   * 1) 查询：时间窗内每条航迹（每架飞机）的最新点，不画航迹线
   */
  async function queryLatestPoints(payload) {
    const body = { mode: 'history', ...buildTimeBody(payload) }
    const data = await api('/api/v1/situation/aircraft/query', {
      method: 'POST',
      body: JSON.stringify(body),
    })
    enterQueryMode()
    tracks.value = []
    points.value = latestPointPerAircraft(data.points || [])
    layers.value.points = true
    lastQuery.value = body
    lastResult.value = {
      pointCount: points.value.length,
      trackCount: 0,
      truncated: !!data.truncated,
    }
    return data
  }

  /**
   * 2) 显示检测点航迹：请求并绘制航迹折线（保留当前点位标绘）
   */
  async function showDetectionTracks(payload) {
    const body = buildTimeBody(payload)
    const data = await api('/api/v1/situation/aircraft/tracks', {
      method: 'POST',
      body: JSON.stringify(body),
    })
    enterQueryMode()
    tracks.value = data.tracks || []
    layers.value.tracks = true
    lastQuery.value = body
    lastResult.value = {
      pointCount: points.value.length,
      trackCount: data.count ?? tracks.value.length,
      truncated: !!data.truncated || lastResult.value.truncated,
    }
    return data
  }

  /**
   * 3) 显示检测点：绘制时间窗内全部检测/观测点
   */
  async function showAllDetectionPoints(payload) {
    const body = { mode: 'history', ...buildTimeBody(payload) }
    const data = await api('/api/v1/situation/aircraft/query', {
      method: 'POST',
      body: JSON.stringify(body),
    })
    enterQueryMode()
    tracks.value = []
    points.value = data.points || []
    layers.value.points = true
    lastQuery.value = body
    lastResult.value = {
      pointCount: data.count ?? points.value.length,
      trackCount: 0,
      truncated: !!data.truncated,
    }
    return data
  }

  function startRealtime() {
    mode.value = 'realtime'
    tracks.value = []
    lastResult.value = { pointCount: 0, trackCount: 0, truncated: false }
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
    tracks.value = []
    lastResult.value = { pointCount: 0, trackCount: 0, truncated: false }
  }

  return {
    mode,
    points,
    tracks,
    lastQuery,
    lastResult,
    layers,
    queryLatestPoints,
    showDetectionTracks,
    showAllDetectionPoints,
    startRealtime,
    stopRealtime,
    resumeRealtime,
    clearPlot,
  }
})
