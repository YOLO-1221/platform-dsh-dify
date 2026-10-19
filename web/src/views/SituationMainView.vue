<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CesiumViewer from '@/modules/cesiumRender/CesiumViewer.vue'
import VisMissionTimeline from '@/modules/taskTrack/components/VisMissionTimeline.vue'
import { isAdmin, setToken } from '@/api/http'
import { useSituationStore } from '@/stores/situation'
import { useTaskTrackStore } from '@/stores/taskTrack'
import { useAiChatStore } from '@/stores/aiChat'

const router = useRouter()
const route = useRoute()
const admin = isAdmin()

const situation = useSituationStore()
const taskTrack = useTaskTrackStore()
const chat = useAiChatStore()

const chatOpen = ref(true)
const queryText = ref('我要查询实时态势信息')
const formAircraftId = ref('')
const queryLoading = ref(false)
const formRange = ref([])

function defaultRange() {
  const end = new Date()
  const start = new Date(end.getTime() - 2 * 60 * 60 * 1000)
  return [start, end]
}
formRange.value = defaultRange()

const currentFrameTimeMs = computed(() => {
  const frame = taskTrack.frames[taskTrack.currentFrame]
  return frame?.timeMs ?? null
})

const currentImageUrl = computed(() => {
  const frame = taskTrack.frames[taskTrack.currentFrame]
  return frame?.imageUrl || ''
})

const queryHint = computed(() => {
  const r = situation.lastResult
  if (situation.mode !== 'query') {
    return '①查询：每机最新点 ②显示检测点航迹：画折线 ③显示检测点：全部点。进入查询模式后暂停实时刷新。'
  }
  const parts = [`点 ${r.pointCount}`, `航迹 ${r.trackCount}`]
  if (r.truncated) parts.push('已截断')
  return parts.join(' · ')
})

onMounted(async () => {
  if (route.query.need_admin === '1') {
    window.alert('Dify 注册与日志仅管理员可用，请使用 admin/admin 重新登录。')
    router.replace({ path: '/', query: {} })
  }
  situation.startRealtime()
  await taskTrack.loadTasks()
})

function logout() {
  setToken('')
  router.push('/login')
}

function requireRange() {
  const [start, end] = formRange.value || []
  if (!start || !end) {
    window.alert('请选择开始与结束时间')
    return null
  }
  return {
    start_time: start,
    end_time: end,
    aircraft_id: formAircraftId.value || undefined,
  }
}

async function runSituationAction(action) {
  const payload = requireRange()
  if (!payload) return
  queryLoading.value = true
  try {
    await action(payload)
  } catch (e) {
    window.alert(e.message || '操作失败')
  } finally {
    queryLoading.value = false
  }
}

/** 1) 查询：每条航迹最新点 */
function onQuery() {
  return runSituationAction((p) => situation.queryLatestPoints(p))
}

/** 2) 显示检测点航迹 */
function onShowDetectionTracks() {
  return runSituationAction((p) => situation.showDetectionTracks(p))
}

/** 3) 显示检测点：全部点 */
function onShowAllDetectionPoints() {
  return runSituationAction((p) => situation.showAllDetectionPoints(p))
}

async function onShowTasks() {
  taskTrack.panelOpen = true
  await taskTrack.loadTasks()
}

async function onSelectTask(taskId) {
  await taskTrack.selectTask(taskId)
}

async function onSendChat() {
  if (!queryText.value.trim()) return
  const { events } = await chat.send(queryText.value.trim())
  const answer = [...events].reverse().find((e) => e.event_type === 'answer')
  const payload = answer?.business_payload
  if (!payload) return
  if (payload.type === 'aircraft_situation') {
    situation.mode = 'query'
    situation.stopRealtime()
    situation.points = payload.data?.points || []
    situation.tracks = payload.data?.tracks || situation.tracks
  }
  if (payload.type === 'task_list') {
    taskTrack.panelOpen = true
    taskTrack.tasks = payload.data?.tasks || []
  }
}
</script>

<template>
  <div class="main-layout">
    <header class="toolbar">
      <div class="brand">Platform2 空域态势</div>
      <div class="toolbar-actions">
        <el-tag :type="situation.mode === 'query' ? 'warning' : 'success'" size="small">
          {{ situation.mode === 'query' ? '查询模式' : '实时模式' }}
        </el-tag>
        <el-button size="small" @click="situation.resumeRealtime()">恢复实时</el-button>
        <el-button size="small" @click="situation.layers.points = !situation.layers.points">
          点位 {{ situation.layers.points ? '开' : '关' }}
        </el-button>
        <el-button size="small" @click="situation.layers.tracks = !situation.layers.tracks">
          航迹 {{ situation.layers.tracks ? '开' : '关' }}
        </el-button>
        <el-button size="small" @click="situation.clearPlot()">清空标绘</el-button>
        <el-button size="small" type="primary" @click="onShowTasks">任务列表</el-button>
        <el-button size="small" @click="chatOpen = !chatOpen">对话</el-button>
        <el-button v-if="admin" size="small" text @click="router.push('/admin/dify')">
          Dify管理
        </el-button>
        <el-button v-if="admin" size="small" text @click="router.push('/admin/logs')">
          日志
        </el-button>
        <el-tag size="small" :type="admin ? 'success' : 'info'">
          {{ admin ? '管理员' : '操作员' }}
        </el-tag>
        <el-button size="small" text @click="logout">退出</el-button>
      </div>
    </header>

    <aside class="side-panel">
      <h3>态势查询</h3>
      <label>时间范围</label>
      <el-date-picker
        v-model="formRange"
        type="datetimerange"
        size="small"
        style="width: 100%"
        range-separator="至"
        start-placeholder="开始"
        end-placeholder="结束"
        :clearable="false"
      />
      <label class="mt-label">飞机编号</label>
      <el-input v-model="formAircraftId" placeholder="可选，如 UA001" size="small" clearable />
      <el-button
        class="mt"
        type="primary"
        style="width: 100%"
        size="small"
        :loading="queryLoading"
        @click="onQuery"
      >
        查询
      </el-button>
      <el-button
        class="mt"
        style="width: 100%"
        size="small"
        :loading="queryLoading"
        @click="onShowDetectionTracks"
      >
        显示检测点航迹
      </el-button>
      <el-button
        class="mt"
        style="width: 100%"
        size="small"
        :loading="queryLoading"
        @click="onShowAllDetectionPoints"
      >
        显示检测点
      </el-button>
      <p class="hint">{{ queryHint }}</p>
    </aside>

    <main class="map-area">
      <CesiumViewer
        :points="situation.points"
        :tracks="situation.tracks"
        :track="taskTrack.track"
        :current-frame-time-ms="currentFrameTimeMs"
        :show-points="situation.layers.points"
        :show-tracks="situation.layers.tracks"
      />
      <div v-if="currentImageUrl" class="image-preview">
        <img :src="currentImageUrl" alt="当前帧图像" />
      </div>
    </main>

    <footer class="timeline-area">
      <VisMissionTimeline
        :frames="taskTrack.frames"
        :current-frame="taskTrack.currentFrame"
        :task-start="taskTrack.selectedTask?.start_time || ''"
        :task-end="taskTrack.selectedTask?.end_time || ''"
        @update:current-frame="taskTrack.setCurrentFrame"
      />
    </footer>

    <aside v-if="chatOpen" class="chat-panel">
      <h3>AI 对话</h3>
      <div class="chat-log">
        <div v-for="(m, i) in chat.messages" :key="i" class="msg" :class="m.role">
          <strong>{{ m.role === 'user' ? '我' : '助手' }}</strong>
          <div>{{ m.content }}</div>
        </div>
        <div v-for="(e, i) in chat.events.filter((x) => x.event_type !== 'answer')" :key="'e'+i" class="evt">
          [{{ e.event_type }}] {{ e.content || e.tool_name || '' }}
        </div>
      </div>
      <el-input v-model="queryText" type="textarea" :rows="3" />
      <div class="mt toolbar-actions">
        <el-button type="primary" size="small" :loading="chat.streaming" @click="onSendChat">发送</el-button>
        <el-button size="small" @click="chat.stop()">停止</el-button>
        <el-button size="small" @click="chat.clear()">清空</el-button>
      </div>
    </aside>

    <el-drawer v-model="taskTrack.panelOpen" title="任务列表" size="360px" direction="rtl">
      <div class="task-drawer">
        <div
          v-for="t in taskTrack.tasks"
          :key="t.id"
          class="task-item"
          :class="{ active: t.id === taskTrack.selectedTaskId }"
          @click="onSelectTask(t.id)"
        >
          <div>{{ t.name }}</div>
          <small>{{ t.status }} · {{ t.start_time }}</small>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.main-layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  grid-template-rows: 52px 1fr 140px;
  height: 100%;
  gap: 0;
}

.main-layout:has(.chat-panel) {
  grid-template-columns: 260px 1fr 320px;
}

.toolbar {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid var(--border-color);
  background: var(--panel-bg);
}

.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.brand {
  font-weight: 700;
  letter-spacing: 0.04em;
}

.side-panel,
.chat-panel {
  background: var(--panel-bg-elevated);
  border-right: 1px solid var(--border-color);
  padding: 14px;
  overflow: auto;
}

.chat-panel {
  border-right: none;
  border-left: 1px solid var(--border-color);
  grid-row: 2 / 3;
  grid-column: 3;
}

.side-panel {
  grid-row: 2 / 3;
  grid-column: 1;
}

.map-area {
  grid-row: 2 / 3;
  grid-column: 2;
  position: relative;
  min-height: 0;
}

.timeline-area {
  grid-column: 1 / -1;
  background: var(--panel-bg);
  border-top: 1px solid var(--border-color);
}

.mt { margin-top: 10px; }
.mt-label { display: block; margin-top: 10px; margin-bottom: 4px; font-size: 12px; }
.query-split { display: flex; gap: 8px; }
.query-split .el-button { flex: 1; }
.hint { color: var(--text-muted); font-size: 12px; line-height: 1.5; margin-top: 10px; }
.side-panel label { display: block; margin-bottom: 4px; font-size: 12px; }
.chat-log { height: 46%; overflow: auto; margin-bottom: 10px; font-size: 13px; }
.msg { margin-bottom: 8px; }
.msg.user { color: var(--accent); }
.evt { color: var(--text-muted); font-size: 12px; margin-bottom: 4px; }
.image-preview {
  position: absolute;
  right: 12px;
  bottom: 12px;
  width: 220px;
  border: 1px solid var(--border-color);
  background: #000;
}
.image-preview img { width: 100%; display: block; }
.task-drawer { padding: 0 4px; }
.task-item {
  padding: 10px;
  border: 1px solid var(--border-color-soft);
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
}
.task-item.active { border-color: var(--accent); }
.task-item small { color: var(--text-secondary); }
</style>
