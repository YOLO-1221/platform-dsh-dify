<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'
import * as Cesium from 'cesium'
import 'cesium/Build/Cesium/Widgets/widgets.css'

const props = defineProps({
  points: { type: Array, default: () => [] },
  track: { type: Object, default: null },
  currentFrameTimeMs: { type: Number, default: null },
  showPoints: { type: Boolean, default: true },
  showTracks: { type: Boolean, default: true },
})

const containerRef = ref(null)
let viewer = null
let pointEntities = []
let trackEntity = null

function clearPoints() {
  pointEntities.forEach((e) => viewer.entities.remove(e))
  pointEntities = []
}

function renderPoints() {
  if (!viewer) return
  clearPoints()
  if (!props.showPoints) return
  for (const p of props.points) {
    pointEntities.push(
      viewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(p.lon, p.lat, p.alt || 8000),
        point: {
          pixelSize: 10,
          color: Cesium.Color.fromCssColorString('#38bdf8'),
          outlineColor: Cesium.Color.WHITE,
          outlineWidth: 1,
        },
        label: {
          text: p.aircraft_id || '',
          font: '12px sans-serif',
          fillColor: Cesium.Color.WHITE,
          pixelOffset: new Cesium.Cartesian2(0, -16),
          showBackground: true,
          backgroundColor: Cesium.Color.fromCssColorString('#0f172acc'),
        },
      }),
    )
  }
}

function renderTrack() {
  if (!viewer) return
  if (trackEntity) {
    viewer.entities.remove(trackEntity)
    trackEntity = null
  }
  if (!props.showTracks || !props.track?.points?.length) return

  let pts = props.track.points
  if (props.currentFrameTimeMs != null) {
    pts = pts.filter((p) => p.time_ms <= props.currentFrameTimeMs)
  }
  if (pts.length < 2) return

  trackEntity = viewer.entities.add({
    polyline: {
      positions: pts.map((p) => Cesium.Cartesian3.fromDegrees(p.lon, p.lat, p.alt || 8000)),
      width: 3,
      material: Cesium.Color.fromCssColorString('#fbbf24'),
    },
  })
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
  })
  viewer.camera.setView({
    destination: Cesium.Cartesian3.fromDegrees(116.4, 39.9, 1200000),
  })
  renderPoints()
  renderTrack()
})

onUnmounted(() => {
  viewer?.destroy()
  viewer = null
})

watch(() => [props.points, props.showPoints], renderPoints, { deep: true })
watch(() => [props.track, props.currentFrameTimeMs, props.showTracks], renderTrack, { deep: true })
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
