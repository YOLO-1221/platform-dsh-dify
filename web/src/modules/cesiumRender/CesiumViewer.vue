<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'
import * as Cesium from 'cesium'
import 'cesium/Build/Cesium/Widgets/widgets.css'

/** 航迹配色（多机区分） */
const TRACK_COLORS = ['#fbbf24', '#34d399', '#f472b6', '#60a5fa', '#c084fc', '#fb923c']
const POINT_COLOR = '#38bdf8'
const TASK_TRACK_COLOR = '#f59e0b'
/** 实时软航迹最多保留点数（借鉴 gods-eye-view 本地累积 trail） */
const TRAIL_MAX_POINTS = 48
const DEFAULT_ALT = 8000

const props = defineProps({
  points: { type: Array, default: () => [] },
  /** 检测任务单条航迹（时间轴截断用） */
  track: { type: Object, default: null },
  /** 态势多机航迹 */
  tracks: { type: Array, default: () => [] },
  currentFrameTimeMs: { type: Number, default: null },
  showPoints: { type: Boolean, default: true },
  showTracks: { type: Boolean, default: true },
})

const containerRef = ref(null)

let viewer = null
/** @type {Map<string, import('cesium').Entity>} */
const pointById = new Map()
/** @type {Map<string, import('cesium').Entity>} */
const softTrailById = new Map()
/** @type {Map<string, Array<{ lon: number, lat: number, alt: number }>>} */
const softTrailHistory = new Map()
/** @type {Map<string, import('cesium').Entity>} */
const trackById = new Map()
/** @type {import('cesium').Entity | null} */
let taskTrackEntity = null
/** @type {string | null} */
let selectedId = null
let lastFitSignature = ''
let userMovedCamera = false
let removeCameraListener = null
let removeClickHandler = null

function colorForIndex(i) {
  return Cesium.Color.fromCssColorString(TRACK_COLORS[i % TRACK_COLORS.length])
}

function colorForId(id) {
  let h = 0
  const s = String(id || '')
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return colorForIndex(h % TRACK_COLORS.length)
}

function toCartesian(p) {
  return Cesium.Cartesian3.fromDegrees(
    Number(p.lon),
    Number(p.lat),
    Number(p.alt) > 0 ? Number(p.alt) : DEFAULT_ALT,
  )
}

function positionsEqual(a, b) {
  if (!a || !b || a.length !== b.length) return false
  for (let i = 0; i < a.length; i++) {
    if (!Cesium.Cartesian3.equalsEpsilon(a[i], b[i], Cesium.Math.EPSILON3)) return false
  }
  return true
}

function setPolylinePositions(entity, cartesians) {
  if (!entity?.polyline) return
  const prev = entity.polyline.positions?.getValue?.(Cesium.JulianDate.now())
  if (positionsEqual(prev, cartesians)) return
  entity.polyline.positions = cartesians
}

function removeEntityMap(map) {
  if (!viewer) return
  for (const e of map.values()) viewer.entities.remove(e)
  map.clear()
}

function removeSoftTrails() {
  removeEntityMap(softTrailById)
  softTrailHistory.clear()
}

/** 实时/每机最新点：一机一键；全部检测点：同机多点需唯一键 */
function pointKey(p, index, latestOnly) {
  const aid = String(p.aircraft_id || '')
  if (latestOnly && aid) return aid
  if (p.id != null) return String(p.id)
  if (p.observed_at && aid) return `${aid}@${p.observed_at}`
  return `${aid || 'p'}#${index}`
}

function isLatestPerAircraft(points) {
  const ids = new Set()
  for (const p of points || []) {
    const aid = p.aircraft_id
    if (!aid) continue
    if (ids.has(aid)) return false
    ids.add(aid)
  }
  return true
}

function upsertPoint(key, p, labelText) {
  if (!key || !viewer) return
  const position = toCartesian(p)
  const existing = pointById.get(key)
  if (existing) {
    existing.position = position
    if (existing.label) existing.label.text = labelText || ''
    existing.show = props.showPoints
    return existing
  }
  const entity = viewer.entities.add({
    id: `pt:${key}`,
    position,
    point: {
      pixelSize: 10,
      color: Cesium.Color.fromCssColorString(POINT_COLOR),
      outlineColor: Cesium.Color.WHITE,
      outlineWidth: 1,
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
      scaleByDistance: new Cesium.NearFarScalar(1.5e3, 1.4, 8.0e6, 0.6),
    },
    label: {
      text: labelText || '',
      font: '12px sans-serif',
      fillColor: Cesium.Color.WHITE,
      pixelOffset: new Cesium.Cartesian2(0, -16),
      showBackground: true,
      backgroundColor: Cesium.Color.fromCssColorString('#0f172acc'),
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
      scaleByDistance: new Cesium.NearFarScalar(1.5e3, 1.0, 8.0e6, 0.4),
    },
  })
  pointById.set(key, entity)
  return entity
}

function syncSoftTrail(aircraftId, p) {
  if (!viewer || !props.showTracks || !aircraftId) return
  // 有正式航迹数据时不再叠本地软航迹，避免双线
  if ((props.tracks?.length || 0) > 0 || props.track?.points?.length) return

  const pos = { lon: Number(p.lon), lat: Number(p.lat), alt: Number(p.alt) || DEFAULT_ALT }
  let hist = softTrailHistory.get(aircraftId)
  if (!hist) {
    hist = []
    softTrailHistory.set(aircraftId, hist)
  }
  const last = hist[hist.length - 1]
  if (!last || last.lon !== pos.lon || last.lat !== pos.lat || last.alt !== pos.alt) {
    hist.push(pos)
    if (hist.length > TRAIL_MAX_POINTS) hist.splice(0, hist.length - TRAIL_MAX_POINTS)
  }
  if (hist.length < 2) return

  const cartesians = hist.map(toCartesian)
  const color = colorForId(aircraftId)
  let trail = softTrailById.get(aircraftId)
  if (!trail) {
    trail = viewer.entities.add({
      id: `soft:${aircraftId}`,
      polyline: {
        positions: cartesians,
        width: 3,
        material: new Cesium.PolylineGlowMaterialProperty({
          glowPower: 0.25,
          color: color.withAlpha(0.85),
        }),
        clampToGround: false,
        arcType: Cesium.ArcType.NONE,
        depthFailMaterial: color.withAlpha(0.25),
      },
    })
    softTrailById.set(aircraftId, trail)
  } else {
    setPolylinePositions(trail, cartesians)
    trail.show = true
  }
}

function syncPoints() {
  if (!viewer) return
  if (!props.showPoints) {
    for (const e of pointById.values()) e.show = false
    for (const e of softTrailById.values()) e.show = false
    return
  }

  const points = props.points || []
  const latestOnly = isLatestPerAircraft(points)
  if (!latestOnly) removeSoftTrails()

  const seen = new Set()
  points.forEach((p, index) => {
    const key = pointKey(p, index, latestOnly)
    if (!key) return
    seen.add(key)
    const label = String(p.aircraft_id || '')
    upsertPoint(key, p, label)
    if (latestOnly && p.aircraft_id) syncSoftTrail(String(p.aircraft_id), p)
  })

  for (const [key, entity] of pointById) {
    if (!seen.has(key)) {
      viewer.entities.remove(entity)
      pointById.delete(key)
      if (selectedId === key) selectedId = null
    }
  }

  if (latestOnly) {
    const liveAids = new Set(
      points.map((p) => String(p.aircraft_id || '')).filter(Boolean),
    )
    for (const [aid, trail] of softTrailById) {
      if (!liveAids.has(aid)) {
        viewer.entities.remove(trail)
        softTrailById.delete(aid)
        softTrailHistory.delete(aid)
      }
    }
  }
}

function upsertTrackLine(id, pts, color, width, keyPrefix) {
  if (!viewer || pts.length < 2) {
    const existing = trackById.get(id)
    if (existing) {
      viewer.entities.remove(existing)
      trackById.delete(id)
    }
    return
  }
  const cartesians = pts.map(toCartesian)
  let entity = trackById.get(id)
  if (!entity) {
    entity = viewer.entities.add({
      id: `${keyPrefix}:${id}`,
      polyline: {
        positions: cartesians,
        width,
        material: new Cesium.PolylineGlowMaterialProperty({
          glowPower: 0.18,
          color: color.withAlpha(0.95),
        }),
        clampToGround: false,
        arcType: Cesium.ArcType.NONE,
        depthFailMaterial: color.withAlpha(0.35),
      },
    })
    trackById.set(id, entity)
  } else {
    setPolylinePositions(entity, cartesians)
    entity.polyline.width = width
    entity.show = true
  }
}

function syncSituationTracks() {
  if (!viewer) return
  if (!props.showTracks) {
    for (const e of trackById.values()) e.show = false
    return
  }

  const situationTracks = Array.isArray(props.tracks) ? props.tracks : []
  const seen = new Set()
  situationTracks.forEach((tr, i) => {
    const id = String(tr?.aircraft_id || `track-${i}`)
    seen.add(id)
    upsertTrackLine(id, tr?.points || [], colorForIndex(i), 4, 'trk')
  })

  for (const [id, entity] of trackById) {
    if (!seen.has(id)) {
      viewer.entities.remove(entity)
      trackById.delete(id)
    }
  }

  if (situationTracks.length > 0) {
    // 正式航迹就绪后清掉软航迹，避免重叠
    removeSoftTrails()
  }
}

function syncTaskTrack() {
  if (!viewer) return
  const raw = props.track?.points || []
  let pts = raw
  if (props.currentFrameTimeMs != null && raw.length) {
    pts = raw.filter((p) => p.time_ms <= props.currentFrameTimeMs)
  }

  if (!props.showTracks || pts.length < 2) {
    if (taskTrackEntity) {
      viewer.entities.remove(taskTrackEntity)
      taskTrackEntity = null
    }
    return
  }

  const cartesians = pts.map(toCartesian)
  const color = Cesium.Color.fromCssColorString(TASK_TRACK_COLOR)
  if (!taskTrackEntity) {
    taskTrackEntity = viewer.entities.add({
      id: 'task-track',
      polyline: {
        positions: cartesians,
        width: 3,
        material: new Cesium.PolylineGlowMaterialProperty({
          glowPower: 0.22,
          color: color.withAlpha(0.95),
        }),
        clampToGround: false,
        arcType: Cesium.ArcType.NONE,
        depthFailMaterial: color.withAlpha(0.35),
      },
    })
  } else {
    setPolylinePositions(taskTrackEntity, cartesians)
    taskTrackEntity.show = true
  }
}

function dataFitSignature() {
  const pointIds = (props.points || [])
    .map((p) => p.aircraft_id)
    .filter(Boolean)
    .sort()
    .join(',')
  const trackIds = (props.tracks || [])
    .map((t) => t.aircraft_id)
    .filter(Boolean)
    .sort()
    .join(',')
  const taskId = props.track?.aircraft_id || ''
  const taskLen = props.track?.points?.length || 0
  return `${pointIds}|${(props.points || []).length}|${trackIds}|${(props.tracks || []).length}|${taskId}:${taskLen}`
}

function collectFitPositions() {
  const positions = []
  for (const p of props.points || []) positions.push(toCartesian(p))
  for (const tr of props.tracks || []) {
    for (const p of tr.points || []) positions.push(toCartesian(p))
  }
  if (props.track?.points?.length) {
    let pts = props.track.points
    if (props.currentFrameTimeMs != null) {
      pts = pts.filter((p) => p.time_ms <= props.currentFrameTimeMs)
    }
    for (const p of pts) positions.push(toCartesian(p))
  }
  return positions
}

function flyToData({ force = false } = {}) {
  if (!viewer) return
  const signature = dataFitSignature()
  if (!force && signature === lastFitSignature) return
  if (!force && userMovedCamera && lastFitSignature) return

  const positions = collectFitPositions()
  if (positions.length < 1) return

  lastFitSignature = signature
  userMovedCamera = false
  const bs = Cesium.BoundingSphere.fromPoints(positions)
  const range = Math.max(bs.radius * 4, 2500)
  viewer.camera.flyToBoundingSphere(bs, {
    duration: 0.8,
    offset: new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(-45), range),
  })
}

function focusAircraft(id) {
  if (!viewer || !id) return
  const entity = pointById.get(id)
  const pos = entity?.position?.getValue?.(Cesium.JulianDate.now())
  if (!pos) return
  selectedId = id
  for (const [aid, e] of pointById) {
    if (e.point) {
      e.point.pixelSize = aid === id ? 14 : 10
      e.point.outlineWidth = aid === id ? 2 : 1
    }
  }
  const range = 18000
  viewer.camera.flyToBoundingSphere(new Cesium.BoundingSphere(pos, 1), {
    duration: 0.6,
    offset: new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(-35), range),
  })
}

function syncAll() {
  syncPoints()
  syncSituationTracks()
  syncTaskTrack()
}

onMounted(() => {
  viewer = new Cesium.Viewer(containerRef.value, {
    animation: false,
    timeline: false,
    baseLayerPicker: false,
    geocoder: false,
    homeButton: false,
    sceneModePicker: false,
    navigationHelpButton: false,
    fullscreenButton: false,
    infoBox: false,
    selectionIndicator: false,
    requestRenderMode: true,
    maximumRenderTimeChange: Infinity,
  })
  viewer.scene.globe.depthTestAgainstTerrain = false
  viewer.scene.fog.enabled = false
  viewer.camera.setView({
    destination: Cesium.Cartesian3.fromDegrees(116.4, 39.9, 1200000),
  })

  removeCameraListener = viewer.camera.moveEnd.addEventListener(() => {
    // 用户拖拽后不再被实时轮询强行拉回
    userMovedCamera = true
  })

  const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)
  handler.setInputAction((movement) => {
    const picked = viewer.scene.pick(movement.position)
    const id = picked?.id?.id
    if (typeof id === 'string' && id.startsWith('pt:')) {
      focusAircraft(id.slice(3))
      userMovedCamera = true
    }
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK)
  removeClickHandler = () => handler.destroy()

  syncAll()
  requestAnimationFrame(() => flyToData({ force: true }))
})

onUnmounted(() => {
  removeCameraListener?.()
  removeClickHandler?.()
  pointById.clear()
  softTrailById.clear()
  softTrailHistory.clear()
  trackById.clear()
  taskTrackEntity = null
  viewer?.destroy()
  viewer = null
})

watch(
  () => [props.points, props.showPoints, props.showTracks],
  () => {
    syncPoints()
    if (!props.showTracks) {
      for (const e of softTrailById.values()) e.show = false
    }
    viewer?.scene?.requestRender?.()
  },
  { deep: true },
)

watch(
  () => [props.tracks, props.track, props.currentFrameTimeMs, props.showTracks],
  () => {
    syncSituationTracks()
    syncTaskTrack()
    viewer?.scene?.requestRender?.()
  },
  { deep: true },
)

watch(
  () => dataFitSignature(),
  (sig, prev) => {
    if (!sig || sig === prev) return
    // 集合变化（查询结果/任务航迹）才自动框选；实时点漂移不抢相机
    const prevParts = String(prev || '').split('|')
    const nextParts = String(sig).split('|')
    const setChanged =
      prevParts[0] !== nextParts[0] ||
      prevParts[2] !== nextParts[2] ||
      prevParts[4] !== nextParts[4]
    if (setChanged) {
      userMovedCamera = false
      requestAnimationFrame(() => flyToData({ force: true }))
    }
  },
)
</script>

<template>
  <div ref="containerRef" class="cesium-host" />
</template>

<style scoped>
.cesium-host {
  width: 100%;
  height: 100%;
}
</style>
