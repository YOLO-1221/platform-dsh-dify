<script setup>
import { formatReconTime } from '../utils/missionTime.js'
import { useVisTimeline } from '../composables/useVisTimeline.js'
import TimelineOverviewBar from './TimelineOverviewBar.vue'

const props = defineProps({
  frames: { type: Array, default: () => [] },
  currentFrame: { type: Number, required: true },
  taskStart: { type: String, default: '' },
  taskEnd: { type: String, default: '' },
  compact: { type: Boolean, default: false },
  liveReceiving: { type: Boolean, default: false },
})

const emit = defineEmits(['update:currentFrame'])

const {
  containerRef,
  overviewWindowStyle,
  displayRange,
  fitAll,
  zoomInView,
  zoomOutView,
  onOverviewClick,
} = useVisTimeline(props, emit)

defineExpose({ fitAll, zoomInView, zoomOutView })
</script>

<template>
  <div class="vis-mission-timeline" :class="{ compact }">
    <div v-if="!compact" class="timeline-bar">
      <span class="label">时间轴</span>
      <span class="range">{{ formatReconTime(displayRange.start) }} ~ {{ formatReconTime(displayRange.end) }}</span>
      <span v-if="frames.length" class="frame-tag">{{ currentFrame + 1 }} / {{ frames.length }} 帧</span>
    </div>

    <div v-if="!frames.length" class="timeline-empty">
      <span v-if="liveReceiving">实时接收中，等待影像帧…</span>
      <span v-else>暂无影像帧</span>
    </div>

    <template v-else>
      <div v-if="compact" class="timeline-range-hint">
        {{ formatReconTime(displayRange.start) }} ~ {{ formatReconTime(displayRange.end) }}
      </div>
      <div class="timeline-body">
        <div ref="containerRef" class="vis-container" :class="{ compact }" />
        <TimelineOverviewBar :window-style="overviewWindowStyle" @seek="onOverviewClick" />
      </div>
    </template>
  </div>
</template>

<style scoped>
.vis-mission-timeline {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--panel-bg);
  overflow: hidden;
  flex-shrink: 0;
}

.vis-mission-timeline.compact {
  border: none;
  border-radius: 0;
  background: transparent;
  border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}

.timeline-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-color-soft);
  font-size: 12px;
}

.label {
  font-weight: 600;
}

.range {
  flex: 1;
  color: var(--text-secondary);
}

.frame-tag {
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(64, 158, 255, 0.12);
  color: #409eff;
  font-size: 11px;
}

.timeline-range-hint {
  padding: 4px 16px 0;
  font-size: 11px;
  color: var(--text-muted);
  font-family: ui-monospace, Consolas, monospace;
}

.timeline-body {
  display: flex;
  flex-direction: column;
}

.vis-container {
  height: 108px;
  overflow: hidden;
  flex-shrink: 0;
}

.vis-container.compact {
  height: 96px;
}

.timeline-empty {
  padding: 20px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
}

:deep(.vis-custom-time) {
  background-color: transparent !important;
  width: 0 !important;
  z-index: 20;
  pointer-events: none;
}

:deep(.vis-custom-time::after) {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  transform: translateX(-50%);
  width: 2px;
  background-color: #f56c6c;
  pointer-events: none;
}

:deep(.vis-custom-time > div) {
  pointer-events: auto;
  cursor: ew-resize;
}

:deep(.vis-task-bg) {
  background-color: rgba(148, 163, 184, 0.08) !important;
}

:deep(.vis-played) {
  background-color: rgba(64, 158, 255, 0.12) !important;
}

:deep(.vis-panel.vis-center) {
  min-height: 44px;
}

:deep(.vis-item.vis-point.vis-frame-dot) {
  background: none !important;
  border: none !important;
}

:deep(.vis-item.vis-point.vis-frame-dot .vis-item-content) {
  display: none !important;
}

:deep(.vis-item.vis-dot.vis-frame-dot) {
  border-style: solid;
  border-radius: 50%;
  border-width: 5px;
  z-index: 3;
  margin-top: 10px;
}

:deep(.vis-item.vis-dot.vis-frame-single.vis-frame-idle) {
  border-color: #94a3b8;
  opacity: 0.45;
}

:deep(.vis-item.vis-dot.vis-frame-single.vis-frame-reached) {
  border-color: #409eff;
  opacity: 1;
}

:deep(.vis-item.vis-dot.vis-frame-single.vis-frame-current) {
  border-width: 7px;
  border-color: #409eff;
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.25);
}

:deep(.vis-item.vis-dot.vis-frame-multi.vis-frame-idle) {
  border-color: #d4a574;
  opacity: 0.5;
}

:deep(.vis-item.vis-dot.vis-frame-multi.vis-frame-reached) {
  border-color: #e6a23c;
  opacity: 1;
}

:deep(.vis-item.vis-dot.vis-frame-multi.vis-frame-current) {
  border-width: 7px;
  border-color: #e6a23c;
  box-shadow: 0 0 0 3px rgba(230, 162, 60, 0.3);
}
</style>
