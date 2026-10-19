<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, setToken } from '@/api/http'

const router = useRouter()
const username = ref('operator')
const password = ref('operator')
const loading = ref(false)

async function onSubmit() {
  loading.value = true
  try {
    const data = await api('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username: username.value, password: password.value }),
    })
    setToken(data.access_token, data.role)
    router.push('/')
  } catch (e) {
    console.error(e)
    alert(e.message || '登录失败')
  } finally {
    loading.value = false
  }
}

function fillAdmin() {
  username.value = 'admin'
  password.value = 'admin'
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card" header="三维空域态势智能平台">
      <el-form @submit.prevent="onSubmit" label-position="top">
        <el-form-item label="账号">
          <el-input v-model="username" placeholder="operator / admin" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="password" type="password" show-password />
        </el-form-item>
        <el-button type="primary" native-type="submit" style="width: 100%" :loading="loading">
          登录
        </el-button>
        <p class="login-hint">
          操作员 operator/operator；注册 Dify 请用
          <a href="#" @click.prevent="fillAdmin">admin/admin</a>
        </p>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100%;
  display: grid;
  place-items: center;
  background:
    radial-gradient(circle at 20% 20%, rgba(56, 189, 248, 0.18), transparent 40%),
    radial-gradient(circle at 80% 0%, rgba(251, 191, 36, 0.12), transparent 35%),
    linear-gradient(160deg, #020617, #0f172a 60%, #111827);
}

.login-card {
  width: 360px;
  background: rgba(15, 23, 42, 0.92);
  --el-bg-color: transparent;
  --el-text-color-primary: #e2e8f0;
  --el-text-color-regular: #cbd5e1;
  --el-border-color: #334155;
  --el-fill-color-blank: #0f172a;
}
.login-hint {
  margin: 12px 0 0;
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.5;
}
.login-hint a {
  color: #38bdf8;
}
</style>
