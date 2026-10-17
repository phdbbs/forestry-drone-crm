import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { track } from '../api'

// meta.group 用于面包屑与侧边栏分区；meta.title 同时作为文档标题与面包屑末级
// meta.public：不套应用外壳、登录前即可访问
const routes = [
  { path: '/login', component: () => import('../views/Login.vue'), meta: { title: '登录', public: true } },
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '智能工作台', group: '工作台' } },
  { path: '/leads', component: () => import('../views/Leads.vue'), meta: { title: '线索管理', group: '客户中心' } },
  { path: '/opportunities', component: () => import('../views/Opportunities.vue'), meta: { title: '商机管理', group: '客户中心' } },
  { path: '/contacts', component: () => import('../views/Contacts.vue'), meta: { title: '联系人管理', group: '客户中心' } },
  { path: '/customers', component: () => import('../views/Customers.vue'), meta: { title: '客户管理', group: '客户中心' } },
  { path: '/contactlog', component: () => import('../views/ContactLog.vue'), meta: { title: '日常联络', group: '联络管理' } },
  { path: '/followups', component: () => import('../views/Followups.vue'), meta: { title: '联络计划', group: '联络管理' } },
  { path: '/kanban', component: () => import('../views/Kanban.vue'), meta: { title: '看板管理', group: '分析与配置' } },
  { path: '/reports', component: () => import('../views/Reports.vue'), meta: { title: '数据报表', group: '分析与配置' } },
  { path: '/settings', component: () => import('../views/Settings.vue'), meta: { title: '系统设置', group: '分析与配置' } },
  // 兜底：未匹配路由渲染 404 页，而不是空白
  { path: '/:pathMatch(.*)*', component: () => import('../views/NotFound.vue'), meta: { title: '页面不存在' } },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  // 切换路由回到顶部，避免长列表跳详情后位置错乱
  scrollBehavior: () => ({ top: 0 }),
})

// 懒加载分块获取失败（最常见：前端重新部署后，旧标签页仍引用旧 hash 的 chunk，
// 服务器把缺失路径兜底成 index.html，动态 import 报 MIME/解析错误）。
// 表现为"点击菜单毫无反应"。这里自动整页刷新一次拉取新入口；
// 用 sessionStorage 打标防止新版本仍然加载失败时无限刷新循环。
router.onError((error) => {
  const msg = String((error && error.message) || error || '')
  const isChunkFail = /dynamically imported module|Importing a module script failed|error loading dynamically imported module|Unexpected token '<'|Invalid or unexpected token/i.test(msg)
  if (isChunkFail && !window.sessionStorage.getItem('crm_chunk_reloaded')) {
    window.sessionStorage.setItem('crm_chunk_reloaded', '1')
    window.location.reload()
    return
  }
  console.error('[router] 路由组件加载失败:', msg)
})

// 鉴权守卫：未登录只允许停在登录页。
// 状态由后端 /auth/status 决定，前端不自持任何口令，避免"本地以为已登录"的错判。
router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.ready) await auth.fetchStatus()
  const needsLogin = auth.authEnabled && !auth.authenticated
  if (to.meta.public) return needsLogin ? true : { path: '/dashboard' }
  if (needsLogin) return { path: '/login' }
  return true
})

router.afterEach((to) => {
  document.title = (to.meta.title || '') + ' - 林业无人机CRM'
  // 任一页面成功渲染即说明分块已可正常加载，解除刷新保护
  window.sessionStorage.removeItem('crm_chunk_reloaded')
  // 点击埋点：登录页不算业务操作（登录本身由后端记账），404 页也不记
  if (!to.meta.public && to.name !== 'notfound') track(to.meta.title || to.path)
})

export default router
