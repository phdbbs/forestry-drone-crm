<template>
  <div class="page">
    <PageHeader title="工作台" subtitle="线索、商机与今日待办的一眼全览">
      <template #actions>
        <el-button :icon="Refresh" plain :loading="loading" @click="reload">刷新</el-button>
      </template>
    </PageHeader>

    <el-row :gutter="14" class="stat-row">
      <el-col v-for="s in statCards" :key="s.label" :xs="12" :sm="12" :md="6">
        <StatCard v-bind="s" :loading="loading" />
      </el-col>
    </el-row>

    <div class="dash-grid">
      <!-- 左栏 -->
      <div class="dash-col">
        <div class="panel">
          <div class="panel-head">
            <span class="ph-icon ph-icon--danger"><el-icon :size="14"><Warning /></el-icon></span>
            <span class="ph-title">紧急事项</span>
            <span v-if="urgentLeads.length" class="ph-badge danger">{{ urgentLeads.length }}</span>
          </div>
          <div class="panel-body">
            <div v-if="urgentLeads.length" class="list-rows">
              <div v-for="(row, i) in urgentLeads" :key="i" class="list-row row-link" @click="goLead(row)">
                <div class="lr-main">
                  <div class="lr-title">{{ row.title }}</div>
                  <div class="lr-sub muted">{{ row.customer_name || '—' }} · 截止 {{ row.deadline || '—' }}</div>
                </div>
                <span class="lr-level" :class="row.level === '高匹配' ? 'is-hot' : 'is-warm'">{{ row.level || '关注' }}</span>
              </div>
            </div>
            <div v-else class="panel-empty muted">暂无紧急事项</div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-head">
            <span class="ph-icon"><el-icon :size="14"><Lightning /></el-icon></span>
            <span class="ph-title">AI 紧急任务 · 当日跟进方案</span>
            <el-button text size="small" :icon="Refresh" :loading="aiLoading" class="ph-refresh" @click="loadTasks(true)">刷新</el-button>
          </div>
          <div class="panel-body">
            <el-skeleton v-if="aiLoading" animated :rows="4" />
            <template v-else-if="aiTasks.length">
              <div class="list-rows">
                <div v-for="(row, i) in aiTasks" :key="i" class="list-row">
                  <div class="lr-main">
                    <div class="lr-title">{{ row.title }}</div>
                    <div class="lr-sub">{{ row.content }}</div>
                    <div v-if="row.related" class="lr-sub muted">关联：{{ row.related }}</div>
                  </div>
                  <span class="lr-level" :class="row.priority === 'high' ? 'is-hot' : 'is-warm'">
                    {{ row.priority === 'high' ? '高' : '中' }}
                  </span>
                </div>
              </div>
              <div class="muted meta-line">
                生成时间 {{ aiMeta.generated_at || '—' }}<template v-if="aiMeta.source === 'cache'">（缓存，可点刷新）</template>
              </div>
            </template>
            <div v-else class="panel-empty muted">{{ aiError || '暂无 AI 跟进任务' }}</div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-head">
            <span class="ph-icon"><el-icon :size="14"><AlarmClock /></el-icon></span>
            <span class="ph-title">今日联络计划</span>
            <span v-if="todayFollowups.length" class="ph-badge">{{ todayFollowups.length }}</span>
          </div>
          <div class="panel-body">
            <div v-if="todayFollowups.length" class="list-rows">
              <div v-for="(row, i) in todayFollowups" :key="i" class="list-row row-link" @click="goExecute(row)">
                <span class="fu-dot"></span>
                <div class="lr-main">
                  <span class="fu-name">{{ row.contact_name || '—' }}</span>
                  <span class="fu-content">{{ row.content }}</span>
                </div>
              </div>
            </div>
            <div v-else class="panel-empty muted">今日无联络计划</div>
          </div>
        </div>
      </div>

      <!-- 右栏 -->
      <div class="dash-col">
        <div v-if="suggestions.length" class="panel panel--ai">
          <div class="panel-head">
            <span class="ph-icon ph-icon--ai"><el-icon :size="14"><MagicStick /></el-icon></span>
            <span class="ph-title">AI 智能建议</span>
          </div>
          <div class="panel-body">
            <ul class="suggestion-list">
              <li v-for="(s, i) in suggestions.slice(0, 5)" :key="i">
                <span class="sug-idx mono">{{ i + 1 }}</span>
                <span class="sug-text">{{ typeof s === 'string' ? s : s.title || s.text || '' }}</span>
              </li>
            </ul>
          </div>
        </div>

        <div class="panel">
          <div class="panel-head">
            <span class="ph-icon"><el-icon :size="14"><TrendCharts /></el-icon></span>
            <span class="ph-title">最新商机</span>
          </div>
          <div class="panel-body">
            <div v-if="opportunities.length" class="list-rows">
              <div v-for="(row, i) in opportunities" :key="i" class="list-row row-link" @click="goOpp(row)">
                <div class="lr-main lr-title-1line">{{ row.title }}</div>
                <span class="stage-chip">{{ row.stage || '—' }}</span>
              </div>
            </div>
            <div v-else class="panel-empty muted">暂无商机</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Lightning, Warning, AlarmClock, MagicStick, TrendCharts, Refresh } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'
import StatCard from '../components/StatCard.vue'
import { get, getList, post } from '../api'
import { useDictStore, useCrawlStore } from '../stores/app'

const dict = useDictStore()
const crawl = useCrawlStore()
const data = ref({})

const router = useRouter()
const goLead = (row) => row?.id && router.push({ path: '/leads', query: { detail: row.id } })
const goOpp = (row) => row?.id && router.push({ path: '/opportunities', query: { detail: row.id } })
const goExecute = (row) => row?.id && router.push({ path: '/followups', query: { execute: row.id } })
const suggestions = ref([])
const loading = ref(true)

const statCards = computed(() => {
  const s = data.value.stats || {}
  return [
    { label: '活跃线索', value: s.active_leads ?? 0, icon: 'Aim', tone: 'primary' },
    { label: '商机总数', value: s.opportunities ?? 0, icon: 'DataAnalysis', tone: 'info' },
    { label: '今日活动', value: s.today_activities ?? 0, icon: 'Phone', tone: 'warning' },
    { label: '紧急线索', value: s.urgent_leads ?? 0, icon: 'Warning', tone: 'danger', alert: true },
  ]
})

const urgentLeads = computed(() => data.value.urgent_leads || [])
const todayFollowups = computed(() => data.value.today_followups || [])
const opportunities = computed(() => (data.value.opportunities || []).slice(0, 5))

const aiTasks = ref([])
const aiMeta = ref({})
const aiError = ref('')
const aiLoading = ref(false)

async function loadTasks(force) {
  aiLoading.value = true
  aiError.value = ''
  const r = force ? await post('/ai/urgent-tasks/refresh') : await get('/ai/urgent-tasks')
  aiLoading.value = false
  if (!r.ok) { aiError.value = r.error || 'AI 分析失败'; return }
  aiTasks.value = r.tasks || []
  aiMeta.value = { generated_at: r.generated_at, source: r.source }
  if (force) dict.loadOpportunities()
}

async function reload() {
  loading.value = true
  const [d, s] = await Promise.all([get('/dashboard'), getList('/suggestions')])
  loading.value = false
  data.value = d || {}
  suggestions.value = Array.isArray(s) ? s : []
  loadTasks(false)
}

onMounted(async () => {
  const [d, s] = await Promise.all([
    get('/dashboard'),
    getList('/suggestions'),
  ])
  loading.value = false
  data.value = d || {}
  suggestions.value = Array.isArray(s) ? s : []
  const total = (d?.urgent_leads?.length || 0) + (d?.today_followups?.length || 0)
  window.dispatchEvent(new CustomEvent('crm:notif', { detail: total }))
  loadTasks(false)
  crawl.checkRunning()
})

watch(() => crawl.finishedAt, async () => {
  data.value = await get('/dashboard')
})
</script>

<style scoped>
.stat-row { margin-bottom: 14px; }
.stat-row :deep(.el-col) { margin-bottom: 14px; }

/* ---- 双栏 ---- */
.dash-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}
.dash-col { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
@media (max-width: 1100px) { .dash-grid { grid-template-columns: 1fr; } }

/* ---- 面板 ---- */
.panel {
  background: var(--crm-bg-card);
  border: 1px solid var(--crm-border-soft);
  border-radius: var(--crm-radius-lg);
  box-shadow: var(--crm-shadow-xs);
}
.panel--ai { border-left: 3px solid var(--crm-pine-300); }
.panel-head {
  display: flex; align-items: center; gap: 8px;
  padding: 13px 16px;
  border-bottom: 1px solid var(--crm-border-soft);
}
.ph-icon {
  width: 22px; height: 22px; border-radius: 6px;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--crm-pine-25); color: var(--crm-pine-600);
  flex-shrink: 0;
}
.ph-icon--danger { background: var(--crm-rose-50, #fef2f2); color: var(--crm-rose-500); }
.ph-icon--ai { background: var(--crm-sky-50); color: var(--crm-sky-500); }
.ph-title { font-size: 13px; font-weight: 600; color: var(--crm-fg-1); letter-spacing: -0.005em; }
.ph-badge {
  font-family: var(--crm-font-mono); font-size: 11px;
  padding: 1px 7px; border-radius: 8px;
  background: var(--crm-slate-100); color: var(--crm-fg-3);
}
.ph-badge.danger { background: var(--crm-rose-50, #fef2f2); color: var(--crm-rose-500); }
.ph-refresh { margin-left: auto; }
.panel-body { padding: 6px 16px 12px; }
.panel-empty { padding: 24px 0; text-align: center; font-size: 12.5px; }

/* ---- 行式列表 ---- */
.list-rows { display: flex; flex-direction: column; }
.list-row {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--crm-border-soft);
}
.list-row:last-child { border-bottom: none; }
.lr-main { flex: 1; min-width: 0; }
.lr-title { font-size: 13px; font-weight: 500; color: var(--crm-fg-1); line-height: 1.5; }
.lr-title-1line { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.lr-sub { font-size: 12px; color: var(--crm-fg-3); line-height: 1.55; margin-top: 2px; }
.lr-level {
  flex-shrink: 0; margin-top: 1px;
  font-size: 11px; font-weight: 500;
  padding: 1px 8px; border-radius: var(--crm-radius-full);
}
.lr-level.is-hot { background: var(--crm-rose-50, #fef2f2); color: var(--crm-rose-500); }
.lr-level.is-warm { background: var(--crm-amber-50); color: var(--crm-amber-500); }

.meta-line { margin-top: 8px; font-size: 11.5px; }

/* 今日联络 */
.fu-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--crm-pine-500); flex-shrink: 0; margin-top: 8px;
}
.fu-name { font-size: 13px; font-weight: 600; color: var(--crm-pine-600); margin-right: 8px; }
.fu-content { font-size: 12.5px; color: var(--crm-fg-2); line-height: 1.6; }

/* AI 建议 */
.suggestion-list { margin: 0; padding: 0; list-style: none; }
.suggestion-list li {
  display: flex; gap: 10px; align-items: flex-start;
  font-size: 13px; line-height: 1.7; padding: 7px 0;
  border-bottom: 1px dashed var(--crm-border-soft);
  color: var(--crm-fg-2);
}
.suggestion-list li:last-child { border-bottom: none; }
.sug-idx {
  flex-shrink: 0; width: 18px; height: 18px; margin-top: 3px;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 10.5px; font-weight: 600;
  background: var(--crm-pine-25); color: var(--crm-pine-600);
  border-radius: 5px;
}
.sug-text { min-width: 0; }

.stage-chip {
  flex-shrink: 0;
  display: inline-block; padding: 1px 8px;
  font-size: 11.5px; border-radius: var(--crm-radius-full);
  background: var(--crm-slate-100); color: var(--crm-fg-2);
}
</style>

<style scoped>
.row-link { cursor: pointer; transition: background 120ms ease-out; }
.row-link:hover { background: var(--crm-pine-25, #eef7f2); }
</style>
