<template>
  <el-container class="layout">
    <!-- 桌面侧边栏 -->
    <el-aside v-if="!isMobile" :width="collapsed ? '64px' : '208px'" class="sidebar">
      <div class="logo" @click="$router.push('/dashboard')">
        <el-icon :size="22" color="#fff"><Aim /></el-icon>
        <span v-show="!collapsed" class="logo-text">林业无人机CRM</span>
      </div>
      <el-menu :default-active="$route.path" router :collapse="collapsed" class="side-menu" :collapse-transition="false">
        <el-menu-item v-for="n in NAV" :key="n.path" :index="n.path">
          <el-icon><component :is="n.icon" /></el-icon>
          <template #title>{{ n.label }}</template>
        </el-menu-item>
      </el-menu>
      <div class="sidebar-foot" v-show="!collapsed">v4.2 · 李明 · 销售总监</div>
    </el-aside>

    <!-- 移动端抽屉 -->
    <el-drawer v-model="drawerOpen" direction="ltr" size="208px" :with-header="false" v-if="isMobile">
      <div class="logo"><el-icon :size="22" color="#fff"><Aim /></el-icon><span class="logo-text">林业无人机CRM</span></div>
      <el-menu :default-active="$route.path" router class="side-menu" @select="drawerOpen = false">
        <el-menu-item v-for="n in NAV" :key="n.path" :index="n.path">
          <el-icon><component :is="n.icon" /></el-icon>
          <template #title>{{ n.label }}</template>
        </el-menu-item>
      </el-menu>
    </el-drawer>

    <el-container class="main-wrap">
      <el-header class="topbar" height="52px">
        <el-button text @click="toggleSide">
          <el-icon :size="18"><Expand v-if="collapsed || isMobile" /><Fold v-else /></el-icon>
        </el-button>
        <span class="topbar-title">{{ $route.meta.title }}</span>
        <span class="topbar-spacer"></span>
        <el-badge :value="notifCount" :hidden="!notifCount" class="bell">
          <el-icon :size="18"><Bell /></el-icon>
        </el-badge>
        <el-tag size="small" type="info" effect="plain">李明 · 销售总监</el-tag>
      </el-header>
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { Aim, Expand, Fold, Bell } from '@element-plus/icons-vue'

const NAV = [
  { path: '/dashboard', label: '智能工作台', icon: 'Odometer' },
  { path: '/leads', label: '线索管理', icon: 'Aim' },
  { path: '/opportunities', label: '商机管理', icon: 'DataAnalysis' },
  { path: '/contacts', label: '联系人管理', icon: 'User' },
  { path: '/customers', label: '客户管理', icon: 'OfficeBuilding' },
  { path: '/contactlog', label: '日常联络', icon: 'Phone' },
  { path: '/followups', label: '联络计划', icon: 'AlarmClock' },
  { path: '/kanban', label: '看板管理', icon: 'Grid' },
  { path: '/reports', label: '数据报表', icon: 'TrendCharts' },
  { path: '/settings', label: '系统设置', icon: 'Setting' },
]

const collapsed = ref(localStorage.getItem('crm_v2_sidebar') === '1')
const isMobile = ref(window.innerWidth < 768)
const drawerOpen = ref(false)
const notifCount = ref(0)

function toggleSide() {
  if (isMobile.value) { drawerOpen.value = true; return }
  collapsed.value = !collapsed.value
  localStorage.setItem('crm_v2_sidebar', collapsed.value ? '1' : '0')
}
function onResize() {
  const m = window.innerWidth < 768
  if (m && !isMobile.value) drawerOpen.value = false
  // 窗口变窄自动收起侧边栏，变宽自动展开
  if (!m) {
    const narrow = window.innerWidth < 1100
    if (narrow !== collapsed.value && localStorage.getItem('crm_v2_sidebar') === null) collapsed.value = narrow
  }
  isMobile.value = m
}
onMounted(() => {
  window.addEventListener('resize', onResize)
  onResize()
  window.addEventListener('crm:notif', (e) => { notifCount.value = e.detail || 0 })
})
onUnmounted(() => window.removeEventListener('resize', onResize))
</script>

<style>
.layout { height: 100%; }
.sidebar {
  background: #1f2d24; display: flex; flex-direction: column;
  transition: width .2s; overflow: hidden;
}
.logo {
  height: 52px; display: flex; align-items: center; gap: 10px; padding: 0 16px;
  color: #fff; font-weight: 700; font-size: 15px; cursor: pointer; flex-shrink: 0;
  white-space: nowrap; overflow: hidden;
}
.side-menu { border-right: none; background: transparent; flex: 1; }
.side-menu .el-menu-item { color: #b8c7bd; }
.side-menu .el-menu-item:hover { background: rgba(255,255,255,.08); color: #fff; }
.side-menu .el-menu-item.is-active { background: var(--el-color-primary); color: #fff; }
.sidebar-foot { color: #6f8276; font-size: 11px; padding: 12px 16px; white-space: nowrap; }
.main-wrap { min-width: 0; }
.topbar {
  background: #fff; border-bottom: 1px solid #e8ecea;
  display: flex; align-items: center; gap: 12px; padding: 0 16px;
}
.topbar-title { font-size: 16px; font-weight: 600; }
.topbar-spacer { flex: 1; }
.bell { display: flex; align-items: center; }
.main-content { padding: 0; overflow-y: auto; background: #f5f7f6; }
.el-drawer .logo { background: #1f2d24; }
.el-drawer .side-menu .el-menu-item { color: #333; }
</style>
