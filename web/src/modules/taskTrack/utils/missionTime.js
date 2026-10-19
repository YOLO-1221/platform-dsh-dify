import moment from 'moment'

export function formatReconTime(time) {
  return moment(time).format('YYYY-MM-DD HH:mm:ss')
}

export function toTimeMs(time) {
  return moment(time).valueOf()
}

export function clampToTaskRange(time, taskStart, taskEnd) {
  const t = moment(time)
  const start = moment(taskStart)
  const end = moment(taskEnd)
  if (t.isBefore(start)) return start.clone()
  if (t.isAfter(end)) return end.clone()
  return t.clone()
}

/** 时间轴可视范围：任务时段与帧数据取并集，实时帧超出任务结束时自动延展 */
export function getTimelineRange(frames, taskStart, taskEnd) {
  const startMs = toTimeMs(taskStart)
  let endMs = toTimeMs(taskEnd)

  if (frames.length) {
    const lastMs = frames[frames.length - 1].timeMs
    endMs = Math.max(endMs, lastMs)
    const span = Math.max(endMs - startMs, 60_000)
    endMs += Math.max(span * 0.04, 120_000)
  }

  return {
    startMs,
    endMs,
    durationMs: Math.max(endMs - startMs, 1),
  }
}

export function timeToFrameIndex(frames, time, taskStart, taskEnd) {
  if (!frames.length) return 0
  const { startMs, endMs } = getTimelineRange(frames, taskStart, taskEnd)
  const raw = moment(time).valueOf()
  const target = Math.max(startMs, Math.min(endMs, raw))

  let closest = 0
  let minDiff = Infinity
  for (let index = 0; index < frames.length; index++) {
    const diff = Math.abs(frames[index].timeMs - target)
    if (diff < minDiff) {
      minDiff = diff
      closest = index
    }
  }
  return closest
}

export function frameToDate(frames, frameIndex) {
  return new Date(frames[frameIndex]?.timeMs ?? Date.now())
}
