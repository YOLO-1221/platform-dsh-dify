<script setup>
import { onMounted, ref } from 'vue'
import { api } from '@/api/http'

const rows = ref([])

onMounted(async () => {
  const data = await api('/api/v1/ai/tool-calls')
  rows.value = data.items || []
})
</script>

<template>
  <div class="page">
    <h2>对话 / 工具调用日志</h2>
    <el-table :data="rows" style="width: 100%" border>
      <el-table-column prop="created_at" label="时间" min-width="180" />
      <el-table-column prop="session_id" label="会话" min-width="200" />
      <el-table-column prop="tool_name" label="工具" min-width="140" />
      <el-table-column prop="summary" label="摘要" min-width="240" />
    </el-table>
  </div>
</template>

<style scoped>
.page { padding: 24px; }
</style>
