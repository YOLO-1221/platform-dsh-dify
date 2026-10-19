<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/http'

const router = useRouter()
const rows = ref([])
const editingId = ref(null)
const form = ref({
  app_id: '',
  name: '',
  app_type: 'workflow',
  intent_desc: '',
  keywords: '',
  api_key: '',
  enabled: true,
})

const typeOptions = [
  { label: 'Workflow', value: 'workflow' },
  { label: 'Agent', value: 'agent' },
]

const missingKeyCount = computed(
  () => rows.value.filter((r) => r.enabled && !r.api_key).length,
)

async function load() {
  try {
    const data = await api('/api/v1/admin/dify')
    rows.value = data.items || []
  } catch (e) {
    const msg = String(e.message || e)
    if (msg.includes('需要管理员权限') || msg.includes('403')) {
      window.alert('当前账号不是管理员。请退出后用 admin / admin 登录再注册。')
      router.push('/login')
      return
    }
    throw e
  }
}

function resetForm() {
  editingId.value = null
  form.value = {
    app_id: '',
    name: '',
    app_type: 'workflow',
    intent_desc: '',
    keywords: '',
    api_key: '',
    enabled: true,
  }
}

function startEdit(row) {
  editingId.value = row.app_id
  form.value = {
    app_id: row.app_id,
    name: row.name,
    app_type: row.app_type,
    intent_desc: row.intent_desc,
    keywords: row.keywords || '',
    api_key: '',
    enabled: row.enabled,
  }
}

async function save() {
  if (!form.value.app_id?.trim() || !form.value.name?.trim()) {
    window.alert('请填写应用名称和 AppID')
    return
  }
  if (!form.value.keywords?.trim()) {
    window.alert('请填写关键字，dsh 靠它匹配是否调用本应用')
    return
  }
  if (!editingId.value && !form.value.api_key?.trim()) {
    window.alert('请填写 Dify API Key（在 Dify 应用 → API 访问 中复制，以 app- 开头）')
    return
  }
  if (!editingId.value && form.value.enabled && !form.value.api_key.startsWith('app-')) {
    window.alert('API Key 通常以 app- 开头，请从 Dify 控制台重新复制')
    return
  }
  try {
    if (editingId.value) {
      await api(`/api/v1/admin/dify/${encodeURIComponent(editingId.value)}`, {
        method: 'PUT',
        body: JSON.stringify({
          name: form.value.name,
          app_type: form.value.app_type,
          intent_desc: form.value.intent_desc,
          keywords: form.value.keywords,
          enabled: form.value.enabled,
          ...(form.value.api_key ? { api_key: form.value.api_key } : {}),
        }),
      })
    } else {
      await api('/api/v1/admin/dify', {
        method: 'POST',
        body: JSON.stringify(form.value),
      })
    }
    resetForm()
    await load()
  } catch (e) {
    window.alert(e.message || '保存失败')
  }
}

async function toggleEnabled(row, enabled) {
  await api(`/api/v1/admin/dify/${encodeURIComponent(row.app_id)}`, {
    method: 'PUT',
    body: JSON.stringify({ enabled }),
  })
  await load()
}

async function remove(row) {
  if (!window.confirm(`删除垂域应用 ${row.app_id}？`)) return
  await api(`/api/v1/admin/dify/${encodeURIComponent(row.app_id)}`, { method: 'DELETE' })
  if (editingId.value === row.app_id) resetForm()
  await load()
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="header-row">
      <h2>Dify 智能体 / 工作流注册</h2>
      <div class="header-actions">
        <el-tag size="small">仅管理员</el-tag>
        <el-button size="small" tag="a" href="http://127.0.0.1:5001" target="_blank" rel="noopener">
          打开 Dify
        </el-button>
        <el-button size="small" @click="router.push('/')">返回态势</el-button>
        <el-button size="small" @click="router.push('/admin/logs')">工具日志</el-button>
      </div>
    </div>

    <ol class="steps">
      <li>点「打开 Dify」，在控制台新建 Workflow 或 Agent。</li>
      <li>进入该应用 →「API 访问」→ 复制 API Key（<code>app-...</code>）。</li>
      <li>用管理员账号在本页登记：AppID、类型、关键字、API Key，然后点「注册」或先点表格「编辑」补 Key。</li>
      <li>重启 <code>dsh</code> 并新开会话，提问时带上关键字即可调用。</li>
    </ol>
    <p v-if="missingKeyCount > 0" class="warn">
      当前有 {{ missingKeyCount }} 条已启用记录未配置 API Key（可点「编辑」补上），dsh 命中后不会真正请求 Dify。
    </p>

    <div class="form">
      <el-input v-model="form.name" placeholder="应用名称" />
      <el-input
        v-model="form.app_id"
        placeholder="平台内唯一 AppID（可与 Dify 应用名对应）"
        :disabled="!!editingId"
      />
      <el-select v-model="form.app_type" placeholder="类型" style="width: 100%">
        <el-option
          v-for="opt in typeOptions"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>
      <el-input v-model="form.intent_desc" placeholder="意图描述" />
      <el-input v-model="form.keywords" placeholder="关键字，逗号分隔，例如：态势,飞机" />
      <el-input
        v-model="form.api_key"
        type="password"
        show-password
        :placeholder="editingId ? 'API Key（留空不修改）' : 'Dify API Key（app-...）'"
      />
      <div class="form-actions">
        <span>启用</span>
        <el-switch v-model="form.enabled" />
        <el-button type="primary" @click="save">{{ editingId ? '保存修改' : '注册' }}</el-button>
        <el-button v-if="editingId" @click="resetForm">取消编辑</el-button>
      </div>

      <el-table :data="rows" style="width: 100%" border>
        <el-table-column prop="name" label="名称" min-width="120" />
        <el-table-column prop="app_id" label="AppID" min-width="140" />
        <el-table-column prop="app_type" label="类型" width="100" />
        <el-table-column prop="keywords" label="关键字" min-width="140" />
        <el-table-column label="API Key" width="100">
          <template #default="{ row }">
            {{ row.api_key ? '已配置' : '未配置' }}
          </template>
        </el-table-column>
        <el-table-column label="启用" width="90">
          <template #default="{ row }">
            <el-switch :model-value="row.enabled" @change="(v) => toggleEnabled(row, v)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="startEdit(row)">编辑</el-button>
            <el-button size="small" link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 24px; max-width: 960px; }
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.form {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.form-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.steps {
  margin: 12px 0 0;
  padding-left: 20px;
  color: #475569;
  font-size: 13px;
  line-height: 1.7;
}
.steps code {
  font-size: 12px;
  background: #f1f5f9;
  padding: 0 4px;
}
.warn { margin: 8px 0 0; color: #b45309; font-size: 13px; }
</style>
