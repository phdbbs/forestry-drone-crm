<template>
  <el-container class="layout">
    <!-- 桌面侧边栏 -->
    <el-aside
      v-if="!isMobile"
      :width="collapsed ? 'var(--crm-sidebar-width-collapsed)' : 'var(--crm-sidebar-width)'"
      class="sidebar"
      :class="{ 'is-collapsed': collapsed }"
    >
      <div class="brand" @click="$router.push('/dashboard')">
        <div class="brand-mark">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 3 L4 8 v8 l8 5 8-5 V8 Z"/>
            <path d="M12 8 v8 M8 12 h8"/>
          </svg>
        </div>
        <div v-show="!collapsed" class="brand-text">
          <div class="brand-name">林业无人机 CRM</div>
          <div class="brand-tag">v4.3 · Pine</div>
        </div>
      </div>
      <el-scrollbar class="side-scroll">
        <el-menu
          :default-active="$route.path"
          router
          :collapse="collapsed"
          :collapse-transition="false"
          class="side-menu"
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
      <div v-show="!collapsed" class="sidebar-foot">
        <div class="foot-user">
          <el-avatar :size="24" class="foot-avatar">万</el-avatar>
          <div class="foot-meta">
            <div class="foot-name">万升航控</div>
            <div class="foot-role">市场</div>
          </div>
        </div>
      </div>
    </el-aside>

    <!-- 移动端抽屉 -->
    <el-drawer v-model="drawerOpen" direction="ltr" size="240px" :with-header="false" v-if="isMobile">
      <div class="brand brand-drawer">
        <div class="brand-mark"><el-icon :size="18"><Aim /></el-icon></div>
        <div class="brand-text">
          <div class="brand-name">林业无人机 CRM</div>
          <div class="brand-tag">v4.3 · Pine</div>
        </div>
      </div>
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
      <el-header class="topbar" :height="'var(--crm-header-height)'">
        <el-button text circle class="toggle-btn" @click="toggleSide" :title="collapsed ? '展开侧栏' : '收起侧栏'">
          <el-icon :size="18"><Expand v-if="collapsed || isMobile" /><Fold v-else /></el-icon>
        </el-button>
        <el-breadcrumb separator="/" class="crumb">
          <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
          <el-breadcrumb-item v-if="$route.meta.group">{{ $route.meta.group }}</el-breadcrumb-item>
          <el-breadcrumb-item>{{ $route.meta.title }}</el-breadcrumb-item>
        </el-breadcrumb>
        <span class="topbar-spacer"></span>
        <div class="global-search" v-if="!isMobile">
          <el-icon class="gs-icon" :size="14"><Search /></el-icon>
          <input
            ref="gsInput"
            v-model="gsQuery"
            class="gs-input"
            :placeholder="gsHint"
            @input="onGsInput"
            @focus="gsFocused = true"
            @blur="onGsBlur"
            @keydown.esc="gsFocused = false; gsQuery = ''"
            @keydown.enter="goFirst"
          />
          <div v-if="gsFocused && gsResults.length" class="gs-panel">
            <template v-for="g in gsGrouped" :key="g.label">
              <div class="gs-group">{{ g.label }}</div>
              <div v-for="r in g.items" :key="g.label + r.id" class="gs-item" @mousedown.prevent="goResult(r)">
                <span class="gs-title">{{ r.title }}</span>
                <span class="gs-sub muted">{{ r.sub }}</span>
              </div>
            </template>
          </div>
        </div>
        <div class="topbar-actions">
          <el-tooltip content="待办提醒" placement="bottom">
            <el-badge :value="notifCount" :hidden="!notifCount" :offset="[-2, 4]" class="bell">
              <el-button text circle @click="$router.push('/dashboard')">
                <el-icon :size="18"><Bell /></el-icon>
              </el-button>
            </el-badge>
          </el-tooltip>
          <div class="topbar-divider" aria-hidden="true"></div>
          <el-dropdown trigger="click">
            <div class="user-chip">
              <el-avatar :size="26" class="user-avatar">万</el-avatar>
              <div class="user-meta">
                <div class="user-name">万升航控</div>
                <div class="user-role">市场</div>
              </div>
              <el-icon class="user-caret" :size="12"><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item :icon="Setting" @click="$router.push('/settings')">系统设置</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="fade-slow" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
        <el-backtop :right="24" :bottom="24" />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>

// ---- 全局搜索：一次查线索/商机/联系人/客户，点击直达详情 ----
const gsQuery = ref('')
const gsResults = ref([])
const gsFocused = ref(false)
const gsInput = ref(null)
let gsTimer = null
const gsHint = '全局搜索：线索 / 商机 / 联系人 / 客户（按 / 聚焦）'
const gsGrouped = computed(() => {
  const names = { lead: '线索', opportunity: '商机', contact: '联系人', customer: '客户' }
  const order = ['lead', 'opportunity', 'contact', 'customer']
  return order.map((t) => ({ label: names[t], items: gsResults.value.filter((r) => r.type === t) }))
    .filter((g) => g.items.length)
})
function onGsInput() {
  clearTimeout(gsTimer)
  const q = gsQuery.value.trim()
  if (!q) { gsResults.value = []; return }
  gsTimer = setTimeout(async () => {
    const r = await get('/search?q=' + encodeURIComponent(q))
    gsResults.value = (r && !r.error && r.results) || []
  }, 250)
}
function onGsBlur() { setTimeout(() => { gsFocused.value = false }, 150) }
function goFirst() {
  if (gsResults.value.length) goResult(gsResults.value[0])
}
function goResult(r) {
  const pathMap = { lead: '/leads', opportunity: '/opportunities', contact: '/contacts', customer: '/customers' }
  gsFocused.value = false
  gsQuery.value = ''
  gsResults.value = []
  router.push({ path: pathMap[r.type], query: { detail: r.id } })
}
// 快捷键 "/" 聚焦全局搜索
function onGlobalKey(e) {
  if (e.key === '/' && !['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) {
    e.preventDefault()
    gsInput.value?.focus?.()
  }
}
window.addEventListener('keydown', onGlobalKey)
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { get } from './api'
import { Aim, Expand, Fold, Bell, ArrowDown, Setting, Search } from '@element-plus/icons-vue'
const router = useRouter()

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
const isMobile = ref(window.innerWidth <= 768)
const drawerOpen = ref(false)
const notifCount = ref(0)

function toggleSide() {
  if (isMobile.value) { drawerOpen.value = true; return }
  collapsed.value = !collapsed.value
  localStorage.setItem('crm_v2_sidebar', collapsed.value ? '1' : '0')
}
function onResize() {
  const m = window.innerWidth <= 768
  if (m && !isMobile.value) drawerOpen.value = false
  if (!m) {
    const narrow = window.innerWidth < 1180
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
.layout { height: 100%; background: var(--crm-bg-app); }

/* ---------------- 侧边栏 ---------------- */
.sidebar {
  background: var(--crm-bg-card);
  border-right: 1px solid var(--crm-border-soft);
  display: flex; flex-direction: column;
  transition: width var(--crm-dur-base) var(--crm-ease-out);
  overflow: hidden;
}
.brand {
  height: var(--crm-header-height);
  display: flex; align-items: center; gap: 10px;
  padding: 0 18px;
  border-bottom: 1px solid var(--crm-border-soft);
  cursor: pointer; flex-shrink: 0;
  color: var(--crm-pine-600);
  user-select: none;
}
.brand-mark {
  width: 30px; height: 30px; border-radius: 8px;
  background: linear-gradient(135deg, var(--crm-pine-500), var(--crm-pine-700));
  color: #fff; display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 2px 4px rgba(19, 106, 71, 0.20);
}
.brand-text { min-width: 0; overflow: hidden; }
.brand-name {
  font-size: 14px; font-weight: 700; letter-spacing: -0.01em;
  color: var(--crm-fg-1); line-height: 1.2; white-space: nowrap;
}
.brand-tag {
  font-family: var(--crm-font-mono);
  font-size: 10.5px; color: var(--crm-fg-4); letter-spacing: 0.02em;
  margin-top: 1px; white-space: nowrap;
}
.brand-drawer { border-bottom: none; padding: 20px 18px 12px; height: auto; }

.side-scroll { flex: 1; min-height: 0; }
.side-menu { border-right: none; padding: 8px 0; }
.is-collapsed .side-menu { padding: 8px 0 0; }

.sidebar-foot {
  border-top: 1px solid var(--crm-border-soft);
  padding: 10px 14px;
  flex-shrink: 0;
}
.foot-user { display: flex; align-items: center; gap: 10px; }
.foot-avatar {
  background: linear-gradient(135deg, var(--crm-pine-500), var(--crm-pine-700));
  color: #fff; font-size: 11.5px; font-weight: 600; flex-shrink: 0;
}
.foot-meta { min-width: 0; overflow: hidden; }
.foot-name { font-size: 12.5px; font-weight: 500; color: var(--crm-fg-1); line-height: 1.2; }
.foot-role { font-size: 11px; color: var(--crm-fg-4); margin-top: 1px; }

/* ---------------- 主区 ---------------- */
.main-wrap { min-width: 0; }
.topbar {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: saturate(1.4) blur(8px);
  -webkit-backdrop-filter: saturate(1.4) blur(8px);
  border-bottom: 1px solid var(--crm-border-soft);
  display: flex; align-items: center; gap: 12px;
  padding: 0 20px;
  position: sticky; top: 0; z-index: 20;
}
.toggle-btn { color: var(--crm-fg-3) !important; }
.toggle-btn:hover { color: var(--crm-fg-1) !important; background: var(--crm-slate-100) !important; }
.crumb { font-size: 13px; }
.topbar-spacer { flex: 1; }

.topbar-actions { display: flex; align-items: center; gap: 6px; }
.topbar-divider { width: 1px; height: 20px; background: var(--crm-border-hairline); margin: 0 4px; }
.bell { display: flex; align-items: center; }
.bell :deep(.el-badge__content) {
  background: var(--crm-rose-500); border: none;
  font-size: 10px; height: 15px; line-height: 15px; padding: 0 4px;
  font-family: var(--crm-font-mono);
}

.user-chip {
  display: flex; align-items: center; gap: 8px; cursor: pointer;
  padding: 4px 8px 4px 4px; border-radius: var(--crm-radius-md);
  outline: none; transition: background var(--crm-dur-fast) var(--crm-ease-out);
  border: 1px solid transparent;
}
.user-chip:hover { background: var(--crm-slate-100); border-color: var(--crm-border-soft); }
.user-avatar {
  background: linear-gradient(135deg, var(--crm-pine-500), var(--crm-pine-700));
  color: #fff; font-size: 12px; font-weight: 600; flex-shrink: 0;
}
.user-meta { line-height: 1.15; min-width: 0; }
.user-name { font-size: 12.5px; font-weight: 600; color: var(--crm-fg-1); }
.user-role { font-size: 10.5px; color: var(--crm-fg-4); }
.user-caret { color: var(--crm-fg-4); }
@media (max-width: 640px) { .user-meta, .user-caret { display: none; } }

.main-content {
  padding: 0; overflow-y: auto; background: var(--crm-bg-app);
  min-height: 0;
}

/* ---------------- 路由过渡 ---------------- */
.fade-slow-enter-active, .fade-slow-leave-active { transition: opacity 180ms var(--crm-ease-out); }
.fade-slow-enter-from, .fade-slow-leave-to { opacity: 0; }
</style>

<style>
/* 全局搜索（顶栏） */
.global-search { position: relative; width: 300px; }
.global-search .gs-icon { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: var(--crm-fg-4, #a3adba); }
.global-search .gs-input {
  width: 100%; box-sizing: border-box; border: 1px solid var(--crm-border-soft, #e1e6ec);
  border-radius: 8px; background: var(--crm-slate-50, #f6f8fa);
  padding: 6px 10px 6px 30px; font-size: 13px; outline: none; color: var(--crm-fg-1);
  transition: border-color 140ms, background 140ms;
}
.global-search .gs-input:focus { border-color: var(--crm-pine-300, #4f9f76); background: #fff; }
.gs-panel {
  position: absolute; top: calc(100% + 6px); left: 0; right: 0; z-index: 3000;
  background: #fff; border: 1px solid var(--crm-border-soft, #e1e6ec); border-radius: 10px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, .12); max-height: 380px; overflow-y: auto; padding: 6px;
}
.gs-group { font-size: 11px; color: var(--crm-fg-4, #a3adba); padding: 6px 8px 2px; }
.gs-item { display: flex; justify-content: space-between; gap: 8px; padding: 7px 8px; border-radius: 6px; cursor: pointer; }
.gs-item:hover { background: var(--crm-pine-25, #eef7f2); }
.gs-title { font-size: 13px; color: var(--crm-fg-1); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.gs-sub { flex-shrink: 0; }
</style>
