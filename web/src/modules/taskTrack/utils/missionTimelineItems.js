import moment from 'moment'

const STATE = {
  IDLE: 'vis-frame-idle',
  REACHED: 'vis-frame-reached',
  CURRENT: 'vis-frame-current',
}

function frameStateClass(frameIndex, currentFrameIndex) {
  if (frameIndex === currentFrameIndex) return STATE.CURRENT
  if (frameIndex <= currentFrameIndex) return STATE.REACHED
  return STATE.IDLE
}

export function buildFrameDotItem(frame, currentFrameIndex) {
  const multi = frame.imageCount > 1
  const stateClass = frameStateClass(frame.index, currentFrameIndex)
  const timeLabel = moment(frame.timeMs).format('HH:mm:ss')
  return {
    id: `f-${frame.index}`,
    start: new Date(frame.timeMs),
    content: ' ',
    title: multi ? `${timeLabel} · ${frame.imageCount}张` : timeLabel,
    type: 'point',
    className: `vis-frame-dot ${multi ? 'vis-frame-multi' : 'vis-frame-single'} ${stateClass}`,
  }
}

export function buildStaticTimelineItems(frames, taskStartMs, taskEndMs) {
  const items = [
    {
      id: 'task-bg',
      start: new Date(taskStartMs),
      end: new Date(taskEndMs),
      type: 'background',
      className: 'vis-task-bg',
    },
  ]
  for (const frame of frames) {
    items.push(buildFrameDotItem(frame, -1))
  }
  return items
}

export function buildPlayedItem(taskStartMs, playedEndMs) {
  if (!playedEndMs) return null
  return {
    id: 'played',
    start: new Date(taskStartMs),
    end: new Date(playedEndMs),
    type: 'background',
    className: 'vis-played',
  }
}

/** 帧切换时仅返回需要 update 的条目 */
export function diffFrameUpdates(frames, prevFrameIndex, nextFrameIndex, taskStartMs) {
  const updates = []
  const played = buildPlayedItem(taskStartMs, frames[nextFrameIndex]?.timeMs)
  if (played) updates.push(played)

  if (prevFrameIndex < 0) {
    for (const frame of frames) {
      updates.push(buildFrameDotItem(frame, nextFrameIndex))
    }
    return updates
  }

  const lo = Math.min(prevFrameIndex, nextFrameIndex)
  const hi = Math.max(prevFrameIndex, nextFrameIndex)
  for (let i = lo; i <= hi; i++) {
    const frame = frames[i]
    if (frame) updates.push(buildFrameDotItem(frame, nextFrameIndex))
  }
  return updates
}
