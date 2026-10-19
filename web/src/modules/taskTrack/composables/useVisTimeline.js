import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { Timeline } from 'vis-timeline/standalone'
import { DataSet } from 'vis-data'
import 'vis-timeline/styles/vis-timeline-graph2d.min.css'
import {
  buildPlayedItem,
  buildFrameDotItem,
  buildStaticTimelineItems,
  diffFrameUpdates,
} from '../utils/missionTimelineItems.js'
import {
  frameToDate,
  getTimelineRange,
  timeToFrameIndex,
  toTimeMs,
} from '../utils/missionTime.js'

const PLAYHEAD_ID = 'playhead'

export function useVisTimeline(props, emit) {
  const containerRef = ref(null)
  const viewWindow = ref({ start: null, end: null })

  let timeline = null
  let items = null
  let syncing = false
  let lastFrameIndex = -1
  let knownFrameCount = 0
  let viewWindowTouched = false

  const timelineRange = computed(() =>
    getTimelineRange(props.frames, props.taskStart, props.taskEnd),
  )

  const timelineStartMs = computed(() => timelineRange.value.startMs)
  const timelineEndMs = computed(() => timelineRange.value.endMs)
  const timelineDurationMs = computed(() => timelineRange.value.durationMs)

  const displayRange = computed(() => {
    if (!props.frames.length) {
      return { start: props.taskStart, end: props.taskEnd }
    }
    const lastTime = props.frames[props.frames.length - 1].reconTime
    return {
      start: props.taskStart,
      end: toTimeMs(lastTime) > toTimeMs(props.taskEnd) ? lastTime : props.taskEnd,
    }
  })

  const overviewWindowStyle = computed(() => {
    if (!viewWindow.value.start || !viewWindow.value.end) {
      return { left: '0%', width: '100%' }
    }
    const winStart = toTimeMs(viewWindow.value.start)
    const winEnd = toTimeMs(viewWindow.value.end)
    const left = ((winStart - timelineStartMs.value) / timelineDurationMs.value) * 100
    const width = ((winEnd - winStart) / timelineDurationMs.value) * 100
    return {
      left: `${Math.max(0, left)}%`,
      width: `${Math.min(100 - left, width)}%`,
    }
  })

  function resolveFrame(time) {
    return timeToFrameIndex(props.frames, time, props.taskStart, props.taskEnd)
  }

  function snapToFrame(date) {
    if (!props.frames.length) return date
    return frameToDate(props.frames, resolveFrame(date))
  }

  function setPlayheadFrame(frameIndex) {
    if (!timeline || !props.frames.length) return
    timeline.setCustomTime(frameToDate(props.frames, frameIndex), PLAYHEAD_ID)
  }

  function syncTimeline(frameIndex) {
    if (!timeline || !items || !props.frames.length) return

    syncing = true
    setPlayheadFrame(frameIndex)

    if (lastFrameIndex < 0) {
      items.clear()
      items.add(
        buildStaticTimelineItems(
          props.frames,
          timelineStartMs.value,
          timelineEndMs.value,
        ),
      )
      items.update(diffFrameUpdates(props.frames, -1, frameIndex, timelineStartMs.value))
      lastFrameIndex = frameIndex
      syncing = false
      return
    }

    if (lastFrameIndex !== frameIndex) {
      items.update(diffFrameUpdates(props.frames, lastFrameIndex, frameIndex, timelineStartMs.value))
      lastFrameIndex = frameIndex
    }

    syncing = false
  }

  function updateViewWindow() {
    if (!timeline) return
    viewWindow.value = timeline.getWindow()
  }

  function applyTimelineRange({ fitWindow = false } = {}) {
    if (!timeline) return

    const { startMs, endMs, durationMs } = timelineRange.value
    timeline.setOptions({
      min: new Date(startMs),
      max: new Date(endMs),
      zoomMin: Math.max(durationMs * 0.06, 30_000),
      zoomMax: durationMs * 1.05,
    })

    if (fitWindow) {
      syncing = true
      timeline.setWindow(new Date(startMs), new Date(endMs), { animation: false })
      syncing = false
    }
  }

  const timelineHeight = computed(() => (props.compact ? 96 : 108))

  function getTimelineOptions() {
    const { startMs, endMs, durationMs } = timelineRange.value
    return {
      stack: false,
      showCurrentTime: false,
      zoomKey: 'ctrlKey',
      horizontalScroll: true,
      verticalScroll: false,
      orientation: { axis: 'top', item: 'top' },
      height: timelineHeight.value,
      min: new Date(startMs),
      max: new Date(endMs),
      start: new Date(startMs),
      end: new Date(endMs),
      zoomMin: Math.max(durationMs * 0.06, 30_000),
      zoomMax: durationMs * 1.05,
      margin: { item: 6, axis: 8 },
      editable: false,
      selectable: false,
      snap: (date) => snapToFrame(date),
    }
  }

  function bindTimelineEvents() {
    timeline.on('click', (eventProps) => {
      if (syncing || !eventProps.time) return
      emit('update:currentFrame', resolveFrame(eventProps.time))
    })

    timeline.on('timechange', (eventProps) => {
      if (syncing || eventProps.id !== PLAYHEAD_ID) return
      const frame = resolveFrame(eventProps.time)
      syncing = true
      setPlayheadFrame(frame)
      if (lastFrameIndex !== frame) {
        items.update(diffFrameUpdates(props.frames, lastFrameIndex, frame, timelineStartMs.value))
        lastFrameIndex = frame
      }
      syncing = false
      emit('update:currentFrame', frame)
    })

    timeline.on('rangechange', () => {
      if (syncing || !timeline) return
      viewWindowTouched = true
      const window = timeline.getWindow()
      if (
        toTimeMs(window.start) < timelineStartMs.value ||
        toTimeMs(window.end) > timelineEndMs.value
      ) {
        syncing = true
        timeline.setWindow(
          new Date(timelineStartMs.value),
          new Date(timelineEndMs.value),
          { animation: false },
        )
        syncing = false
      }
      updateViewWindow()
    })

    timeline.on('rangechanged', updateViewWindow)
  }

  function appendNewFrames(prevCount) {
    if (!timeline || !items) return

    const newFrames = props.frames.slice(prevCount)
    if (!newFrames.length) return

    items.update({
      id: 'task-bg',
      end: new Date(timelineEndMs.value),
    })
    items.update(
      newFrames.map((frame) => buildFrameDotItem(frame, props.currentFrame)),
    )

    applyTimelineRange({ fitWindow: !viewWindowTouched })
    syncTimeline(props.currentFrame)
    updateViewWindow()
  }

  function initTimeline() {
    if (!containerRef.value || !props.frames.length || !props.taskStart || !props.taskEnd) return

    lastFrameIndex = -1
    knownFrameCount = props.frames.length
    viewWindowTouched = false
    items = new DataSet()
    timeline = new Timeline(containerRef.value, items, getTimelineOptions())
    timeline.addCustomTime(frameToDate(props.frames, props.currentFrame), PLAYHEAD_ID)
    bindTimelineEvents()
    syncTimeline(props.currentFrame)
    updateViewWindow()
  }

  function destroyTimeline() {
    timeline?.destroy()
    timeline = null
    items = null
    lastFrameIndex = -1
    knownFrameCount = 0
    viewWindowTouched = false
    viewWindow.value = { start: null, end: null }
  }

  function fitAll() {
    viewWindowTouched = false
    timeline?.setWindow(
      new Date(timelineStartMs.value),
      new Date(timelineEndMs.value),
      { animation: true },
    )
  }

  function zoomInView() {
    if (!timeline) return
    const w = timeline.getWindow()
    const start = toTimeMs(w.start)
    const end = toTimeMs(w.end)
    const center = (start + end) / 2
    const span = (end - start) * 0.65
    timeline.setWindow(new Date(center - span / 2), new Date(center + span / 2), { animation: true })
  }

  function zoomOutView() {
    if (!timeline) return
    const w = timeline.getWindow()
    const start = toTimeMs(w.start)
    const end = toTimeMs(w.end)
    const center = (start + end) / 2
    const span = Math.min((end - start) * 1.5, timelineDurationMs.value)
    const newStart = Math.max(timelineStartMs.value, center - span / 2)
    const newEnd = Math.min(timelineEndMs.value, center + span / 2)
    timeline.setWindow(new Date(newStart), new Date(newEnd), { animation: true })
  }

  function onOverviewClick(event) {
    if (!props.frames.length) return
    const rect = event.currentTarget.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width))
    const timeMs = timelineStartMs.value + ratio * timelineDurationMs.value
    emit('update:currentFrame', resolveFrame(new Date(timeMs)))
  }

  watch(() => props.currentFrame, (frame) => syncTimeline(frame))

  watch(
    () => [props.frames.length, props.frames.at(-1)?.timeMs, props.taskStart, props.taskEnd],
    ([frameCount]) => {
      if (!props.frames.length || !props.taskStart || !props.taskEnd) {
        destroyTimeline()
        return
      }

      if (!timeline) {
        nextTick(() => initTimeline())
        return
      }

      if (frameCount > knownFrameCount) {
        const prev = knownFrameCount
        knownFrameCount = frameCount
        appendNewFrames(prev)
        applyTimelineRange({ fitWindow: !viewWindowTouched })
        return
      }

      if (frameCount !== knownFrameCount) {
        knownFrameCount = 0
        destroyTimeline()
        nextTick(() => initTimeline())
      }
    },
    { deep: false },
  )

  onMounted(() => {
    if (props.frames.length) initTimeline()
  })

  onUnmounted(() => destroyTimeline())

  return {
    containerRef,
    overviewWindowStyle,
    displayRange,
    fitAll,
    zoomInView,
    zoomOutView,
    onOverviewClick,
  }
}
