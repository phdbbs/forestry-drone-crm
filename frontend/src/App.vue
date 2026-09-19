<template>
  <el-container class="layout">
    <!-- 桌面侧边栏（浅色，分组导航） -->
    <el-aside v-if="!isMobile" :width="collapsed ? '64px' : '216px'" class="sidebar">
      <div class="logo" @click="$router.push('/dashboard')">
        <el-icon :size="20"><Aim /></el-icon>
        <span v-show="!collapsed" class="logo-text">林业无人机CRM</span>
      </div>
      <el-scrollbar class="side-scroll">
        <el-menu
          :default-active="$route.path"
          router
          :collapse="collapsed"
          class="side-menu"
          :collapse-transition="false"
        >
          <template v-for="g in NAV_GROUPS" :key="g.group">
            <el-menu-item-group v-if="!collapsed" :title="g.group">
              <el-menu-item v-for="n in g.items" :key="n.path" :index="n.path">
                <el-icon><component :is="n.icon" /></el-icon>
                <template #title>{{ n.label }}</template>
              </el-menu-item>
            </el-menu-item-group>
            <template v-else>
              <el-menu-item v-for="n in g.items" :key="n.path" :index="n.path">
                <el-icon><component :is="n.icon" /></el-icon>
                <template #title>{{ n.label }}</template>
              </el-menu-item>
            </template>
          </template>
        </el-menu>
      </el-scrollbar>
      <div class="sidebar-foot" v-show="!collapsed">v4.2 · 李明 · 销售总监</div>
    </el-aside>

    <!-- 移动端抽屉 -->
    <el-drawer v-model="drawerOpen" direction="ltr" size="216px" :with-header="false" v-if="isMobile">
      <div class="logo logo-drawer"><el-icon :size="20"><Aim /></el-icon><span class="logo-text">林业无人机CRM</span></div>
      <el-menu :default-active="$route.path" router class="side-menu" @select="drawerOpen = false">
        <template v-for="g in NAV_GROUPS" :key="g.group">
          <el-menu-item-group :title="g.group">
            <el-menu-item v-for="n in g.items" :key="n.path" :index="n.path">
              <el-icon><component :is="n.icon" /></el-icon>
              <template #title>{{ n.label }}</template>
            </el-menu-item>
          </el-menu-item-group>
        </template>
      </el-menu>
    </el-drawer>

    <el-container class="main-wrap">
      <el-header class="topbar" height="52px">
        <el-button text @click="toggleSide">
          <el-icon :size="18"><Expand v-if="collapsed || isMobile" /><Fold v-else /></el-icon>
        </el-button>
        <!-- 面包屑：首页 / 分组 / 当前页 -->
        <el-breadcrumb separator="/" class="crumb">
          <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
          <el-breadcrumb-item v-if="$route.meta.group">{{ $route.meta.group }}</el-breadcrumb-item>
          <el-breadcrumb-item>{{ $route.meta.title }}</el-breadcrumb-item>
        </el-breadcrumb>
        <span class="topbar-spacer"></span>
        <el-tooltip content="待办提醒" placement="bottom">
          <el-badge :value="notifCount" :hidden="!notifCount" class="bell">
            <el-button text circle @click="$router.push('/dashboard')">
              <el-icon :size="18"><Bell /></el-icon>
            </el-button>
          </el-badge>
        </el-tooltip>
        <el-divider direction="vertical" />
        <el-dropdown>
          <span class="user-chip">
            <el-avatar :size="26" class="user-avatar">李</el-avatar>
            <span class="user-name">李明</span>
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="$router.push('/settings')">
                <el-icon><Setting /></el-icon>系统设置
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main class="main-content">
        <router-view />
        <el-backtop :right="24" :bottom="24" />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { Aim, Expand, Fold, Bell, ArrowDown, Setting } from '@element-plus/icons-vue'

// 分组导航：与 router 的 meta.group 保持一致
const NAV_GROUPS = [
  { group: '工作台', items: [{ path: '/dashboard', label: '智能工作台', icon: 'Odometer' }] },
  {
    group: '客户中心',
    items: [
      { path: '/leads', label: '线索管理', icon: 'Aim' },
      { path: '/opportunities', label: '商机管理', icon: 'DataAnalysis' },
      { path: '/contacts', label: '联系人管理', icon: 'User' },
      { path: '/customers', label: '客户管理', icon: 'OfficeBuilding' },
    ],
  },
  {
    group: '联络管理',
    items: [
      { path: '/contactlog', label: '日常联络', icon: 'Phone' },
      { path: '/followups', label: '联络计划', icon: 'AlarmClock' },
    ],
  },
  {
    group: '分析与配置',
    items: [
      { path: '/kanban', label: '看板管理', icon: 'Grid' },
      { path: '/reports', label: '数据报表', icon: 'TrendCharts' },
      { path: '/settings', label: '系统设置', icon: 'Setting' },
    ],
  },
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
function onNotif(e) { notifCount.value = e.detail || 0 }

onMounted(() => {
  window.addEventListener('resize', onResize)
  onResize()
  window.addEventListener('crm:notif', onNotif)
})
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  window.removeEventListener('crm:notif', onNotif)
})
</script>

<style>
.layout { height: 100%; }

/* 浅色侧边栏 */
.sidebar {
  background: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color-lighter);
  display: flex; flex-direction: column;
  transition: width .2s; overflow: hidden;
}
.side-scroll { flex: 1; }
.logo {
  height: 52px; display: flex; align-items: center; gap: 10px; padding: 0 18px;
  color: var(--el-color-primary); font-weight: 700; font-size: 15px; cursor: pointer;
  border-bottom: 1px solid var(--el-border-color-lighter);
  flex-shrink: 0; white-space: nowrap; overflow: hidden;
}
.logo-drawer { border-bottom: none; }
.side-menu { border-right: none; }
.side-menu :deep(.el-menu-item-group__title) {
  padding: 12px 0 4px 18px;
  font-size: 11px; color: var(--el-text-color-placeholder);
  letter-spacing: .04em;
}
.sidebar-foot {
  color: var(--el-text-color-placeholder); font-size: 11px; padding: 10px 18px;
  white-space: nowrap; border-top: 1px solid var(--el-border-color-lighter);
}

.main-wrap { min-width: 0; }
.topbar {
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-lighter);
  display: flex; align-items: center; gap: 10px; padding: 0 16px;
}
.crumb { font-size: 13px; }
.topbar-spacer { flex: 1; }
.bell { display: flex; align-items: center; }
.user-chip {
  display: flex; align-items: center; gap: 8px; cursor: pointer;
  padding: 4px 8px; border-radius: var(--el-border-radius-base);
  color: var(--el-text-color-regular); font-size: 13px; outline: none;
}
.user-chip:hover { background: var(--el-fill-color-light); }
.user-avatar { background: var(--el-color-primary); color: #fff; font-size: 13px; }
.user-name { font-weight: 500; }

.main-content { padding: 0; overflow-y: auto; background: var(--el-bg-color-page); }
</style>
