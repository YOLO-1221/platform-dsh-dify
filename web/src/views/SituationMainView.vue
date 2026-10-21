<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CesiumViewer from '@/modules/cesiumRender/CesiumViewer.vue'
import VisMissionTimeline from '@/modules/taskTrack/components/VisMissionTimeline.vue'
import { isAdmin, setToken } from '@/api/http'
import { useSituationStore } from '@/stores/situation'
import { useTaskTrackStore } from '@/stores/taskTrack'
import { useAiChatStore } from '@/stores/aiChat'
import { collectDoneIds, defaultNextActions } from '@/modules/taskTrack/actionCatalog'
import { applyBusinessPayload as applyWorkflowPayload } from '@/modules/taskTrack/workflowActions'

const router = useRouter()
const route = useRoute()
const admin = isAdmin()

const situation = useSituationStore()
const taskTrack = useTaskTrackStore()
const chat = useAiChatStore()

const chatOpen = ref(true)
const queryText = ref('查询当前检测任务')
const actionLoading = ref('')
/** 对话推荐的下一步：{ id, label, utterance }[] */
const suggestedActions = ref([])

function currentDoneIds() {
  return collectDoneIds(taskTrack.workflowSnapshot())
}

function refreshLocalSuggestions(type) {
  suggestedActions.value = defaultNextActions(type, currentDoneIds())
}

const currentFrameTimeMs = computed(() => {
  const frame = taskTrack.frames[taskTrack.currentFrame]
  return frame?.timeMs ?? null
})

const currentImageUrl = computed(() => {
  const frame = taskTrack.frames[taskTrack.currentFrame]
  return frame?.imageUrl || ''
})

const plotPoints = computed(() => {
  if (situation.mode === 'realtime') return situation.points
  return [...taskTrack.detectionPoints, ...taskTrack.associatedPoints]
})

const plotTracks = computed(() => {
  if (situation.mode === 'realtime') return situation.tracks
  const limit = currentFrameTimeMs.value
  return taskTrack.detectionTracks.map((tr) => ({
    ...tr,
    points: limit == null ? tr.points : (tr.points || []).filter((p) => (p.time_ms ?? 0) <= limit),
  }))
})

const workflowHint = computed(() => {
  if (!taskTrack.selectedTask) {
    return '①查询任务 ②打开任务，再按需加载检测点、检测航迹、检测图像和时空关联态势点。'
  }
  const name = taskTrack.selectedTask.name
  return [
    name,
    `检测点 ${taskTrack.detectionPoints.length}`,
    `航迹 ${taskTrack.detectionTracks.length}`,
    `图像 ${taskTrack.images.length}`,
    `关联态势 ${taskTrack.associatedPoints.length}`,
  ].join(' · ')
})

onMounted(async () => {
  if (route.query.need_admin === '1') {
    window.alert('Dify 注册与日志仅管理员可用，请使用 admin/admin 重新登录。')
    router.replace({ path: '/', query: {} })
  }
  await taskTrack.loadTasks()
})

function enterTaskMode() {
  situation.mode = 'query'
  situation.stopRealtime()
}

function logout() {
  setToken('')
  router.push('/login')
}

async function runWorkflow(name, action) {
  actionLoading.value = name
  try {
    await action()
  } catch (e) {
    window.alert(e.message || '操作失败')
  } finally {
    actionLoading.value = ''
  }
}

function onQueryTasks() {
  return runWorkflow('tasks', async () => {
    await taskTrack.queryTasks()
    refreshLocalSuggestions('task_list')
  })
}

function onOpenTask(taskId) {
  return runWorkflow('open', async () => {
    enterTaskMode()
    await taskTrack.openTask(taskId)
    refreshLocalSuggestions('task_open')
  })
}

function onLoadDetections() {
  return runWorkflow('detections', async () => {
    enterTaskMode()
    await taskTrack.loadDetectionPoints()
    refreshLocalSuggestions('detection_points')
  })
}

function onLoadTracks() {
  return runWorkflow('tracks', async () => {
    enterTaskMode()
    await taskTrack.loadDetectionTracks()
    refreshLocalSuggestions('detection_tracks')
  })
}

function onLoadImages() {
  return runWorkflow('images', async () => {
    enterTaskMode()
    await taskTrack.loadImages()
    refreshLocalSuggestions('detection_images')
  })
}

function onLoadAssociated() {
  return runWorkflow('associated', async () => {
    enterTaskMode()
    await taskTrack.loadAssociatedSituation()
    refreshLocalSuggestions('associated_situation')
  })
}

function onClearPlot() {
  situation.clearPlot()
  taskTrack.clearLayers()
  suggestedActions.value = []
}

function applyBusinessPayload(payload) {
  const result = applyWorkflowPayload(payload, {
    taskTrack,
    enterTaskMode,
    doneIds: currentDoneIds, // hydrate 后再采样，过滤已完成步骤
  })
  if (result) suggestedActions.value = result.nextActions
}

async function onSendChat(text) {
  const content = (typeof text === 'string' ? text : queryText.value).trim()
  if (!content) return
  queryText.value = content
  suggestedActions.value = []
  const done = currentDoneIds()
  const { business_payload } = await chat.send(content, {
    taskId: taskTrack.selectedTaskId,
    done,
  })
  applyBusinessPayload(business_payload)
}

function onSuggestedAction(action) {
  if (!action?.utterance || chat.streaming) return
  return onSendChat(action.utterance)
}

function onClearChat() {
  chat.clear()
  suggestedActions.value = []
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
        <el-button size="small" @click="onClearPlot">清空标绘</el-button>
        <el-button size="small" type="primary" @click="onQueryTasks">查询任务</el-button>
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
      <h3>作业流程</h3>
      <el-button
        type="primary"
        style="width: 100%"
        size="small"
        :loading="actionLoading === 'tasks'"
        @click="onQueryTasks"
      >
        1. 查询任务
      </el-button>
      <p class="step-status">
        2. 打开任务：{{ taskTrack.selectedTask?.name || '未打开' }}
      </p>
      <el-button
        class="mt"
        style="width: 100%"
        size="small"
        :disabled="!taskTrack.selectedTaskId"
        :loading="actionLoading === 'detections'"
        @click="onLoadDetections"
      >
        3. 加载检测点
      </el-button>
      <el-button
        class="mt"
        style="width: 100%"
        size="small"
        :disabled="!taskTrack.selectedTaskId"
        :loading="actionLoading === 'tracks'"
        @click="onLoadTracks"
      >
        4. 加载检测航迹
      </el-button>
      <el-button
        class="mt"
        style="width: 100%"
        size="small"
        :disabled="!taskTrack.selectedTaskId"
        :loading="actionLoading === 'images'"
        @click="onLoadImages"
      >
        5. 加载检测图像
      </el-button>
      <el-button
        class="mt"
        style="width: 100%"
        size="small"
        :disabled="!taskTrack.selectedTaskId"
        :loading="actionLoading === 'associated'"
        @click="onLoadAssociated"
      >
        6. 加载时空关联态势点
      </el-button>
      <p class="hint">{{ workflowHint }}</p>
    </aside>

    <main class="map-area">
      <CesiumViewer
        :points="plotPoints"
        :tracks="plotTracks"
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
      <div v-if="suggestedActions.length" class="suggested">
        <div class="suggested-title">推荐下一步</div>
        <div class="suggested-list">
          <el-button
            v-for="a in suggestedActions"
            :key="a.id"
            size="small"
            :disabled="chat.streaming"
            @click="onSuggestedAction(a)"
          >
            {{ a.label }}
          </el-button>
        </div>
      </div>
      <el-input v-model="queryText" type="textarea" :rows="3" />
      <div class="mt toolbar-actions">
        <el-button type="primary" size="small" :loading="chat.streaming" @click="onSendChat()">发送</el-button>
        <el-button size="small" @click="chat.stop()">停止</el-button>
        <el-button size="small" @click="onClearChat">清空</el-button>
      </div>
    </aside>

    <el-drawer v-model="taskTrack.panelOpen" title="打开任务" size="360px" direction="rtl">
      <div class="task-drawer">
        <div
          v-for="t in taskTrack.tasks"
          :key="t.id"
          class="task-item"
          :class="{ active: t.id === taskTrack.selectedTaskId }"
          @click="onOpenTask(t.id)"
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
.step-status { margin: 10px 0 0; font-size: 13px; }
.suggested { margin-bottom: 10px; }
.suggested-title { font-size: 12px; color: var(--text-muted); margin-bottom: 6px; }
.suggested-list { display: flex; flex-wrap: wrap; gap: 6px; }
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
