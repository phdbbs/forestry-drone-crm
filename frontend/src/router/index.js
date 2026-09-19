import { createRouter, createWebHashHistory } from 'vue-router'

// meta.group 用于面包屑与侧边栏分区；meta.title 同时作为文档标题与面包屑末级
const routes = [
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

router.afterEach((to) => {
  document.title = (to.meta.title || '') + ' - 林业无人机CRM'
})

export default router
