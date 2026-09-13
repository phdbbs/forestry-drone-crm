import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '智能工作台' } },
  { path: '/leads', component: () => import('../views/Leads.vue'), meta: { title: '线索管理' } },
  { path: '/opportunities', component: () => import('../views/Opportunities.vue'), meta: { title: '商机管理' } },
  { path: '/contacts', component: () => import('../views/Contacts.vue'), meta: { title: '联系人管理' } },
  { path: '/customers', component: () => import('../views/Customers.vue'), meta: { title: '客户管理' } },
  { path: '/contactlog', component: () => import('../views/ContactLog.vue'), meta: { title: '日常联络' } },
  { path: '/followups', component: () => import('../views/Followups.vue'), meta: { title: '联络计划' } },
  { path: '/kanban', component: () => import('../views/Kanban.vue'), meta: { title: '看板管理' } },
  { path: '/reports', component: () => import('../views/Reports.vue'), meta: { title: '数据报表' } },
  { path: '/settings', component: () => import('../views/Settings.vue'), meta: { title: '系统设置' } },
]

const router = createRouter({ history: createWebHashHistory(), routes })

router.afterEach((to) => {
  document.title = (to.meta.title || '') + ' - 林业无人机CRM'
})

export default router
