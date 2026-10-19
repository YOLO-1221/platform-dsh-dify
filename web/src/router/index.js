import { createRouter, createWebHistory } from 'vue-router'
import { getToken, isAdmin } from '@/api/http'

const routes = [
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') },
  { path: '/', name: 'main', component: () => import('@/views/SituationMainView.vue') },
  {
    path: '/admin/dify',
    name: 'admin-dify',
    meta: { admin: true },
    component: () => import('@/views/AdminDifyView.vue'),
  },
  {
    path: '/admin/logs',
    name: 'admin-logs',
    meta: { admin: true },
    component: () => import('@/views/AdminLogsView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  if (to.path === '/login') return true
  if (!getToken()) return '/login'
  if (to.meta?.admin && !isAdmin()) return { path: '/', query: { need_admin: '1' } }
  return true
})

export default router
