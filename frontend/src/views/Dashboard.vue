<template>
  <div class="page">
    <el-row :gutter="16" class="card-block">
      <el-col v-for="s in statCards" :key="s.label" :xs="12" :sm="12" :md="6">
        <StatCard v-bind="s" :loading="loading" />
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <!-- 左栏 -->
      <el-col :xs="24" :lg="12">
        <el-card shadow="never" class="card-block">
          <template #header>
            <div class="card-head">
              <el-icon class="head-icon head-icon--danger"><Warning /></el-icon>
              <span>紧急事项</span>
              <el-tag v-if="urgentLeads.length" size="small" type="danger" effect="light" class="head-tag">
                {{ urgentLeads.length }}
              </el-tag>
            </div>
          </template>
          <el-table v-if="urgentLeads.length" :data="urgentLeads" size="small" :show-header="false">
            <el-table-column min-width="220">
              <template #default="{ row }">
                <div class="item-title">{{ row.title }}</div>
                <div class="muted">{{ row.customer_name || '-' }} · 截止 {{ row.deadline || '-' }}</div>
              </template>
            </el-table-column>
            <el-table-column width="86" align="right">
              <template #default="{ row }">
                <el-tag size="small" effect="light" :type="row.level === '高匹配' ? 'danger' : 'warning'">
                  {{ row.level || '关注' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无紧急事项" :image-size="60" />
        </el-card>

        <el-card shadow="never" class="card-block">
          <template #header>
            <div class="card-head">
              <el-icon class="head-icon"><Lightning /></el-icon>
              <span>AI 紧急任务 · 当日跟进方案</span>
              <el-button size="small" :icon="Refresh" :loading="aiLoading" class="head-tag" @click="loadTasks(true)">刷新</el-button>
            </div>
          </template>
          <el-skeleton v-if="aiLoading" animated :rows="4" />
          <template v-else-if="aiTasks.length">
            <el-table :data="aiTasks" size="small" :show-header="false">
              <el-table-column min-width="260">
                <template #default="{ row }">
                  <div class="item-title">{{ row.title }}</div>
                  <div class="muted">{{ row.content }}</div>
                  <div v-if="row.related" class="muted">关联：{{ row.related }}</div>
                </template>
              </el-table-column>
              <el-table-column width="76" align="right">
                <template #default="{ row }">
                  <el-tag size="small" effect="light" :type="row.priority === 'high' ? 'danger' : 'warning'">
                    {{ row.priority === 'high' ? '高' : '中' }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
            <div class="muted meta-line">
              生成时间：{{ aiMeta.generated_at || '-' }}{{ aiMeta.source === 'cache' ? '（缓存，可点刷新）' : '' }}
            </div>
          </template>
          <el-empty v-else :description="aiError || '暂无 AI 跟进任务'" :image-size="60" />
        </el-card>

        <el-card shadow="never">
          <template #header>
            <div class="card-head">
              <el-icon class="head-icon"><AlarmClock /></el-icon>
              <span>今日联络计划</span>
            </div>
          </template>
          <el-table v-if="todayFollowups.length" :data="todayFollowups" size="small" :show-header="false">
            <el-table-column min-width="140">
              <template #default="{ row }">
                <span class="contact-name">{{ row.contact_name || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="content" min-width="220" show-overflow-tooltip />
          </el-table>
          <el-empty v-else description="今日无联络计划" :image-size="60" />
        </el-card>
      </el-col>

      <!-- 右栏 -->
      <el-col :xs="24" :lg="12">
        <el-card v-if="suggestions.length" shadow="never" class="card-block suggestions-card">
          <template #header>
            <div class="card-head">
              <el-icon class="head-icon"><MagicStick /></el-icon>
              <span>AI 智能建议</span>
            </div>
          </template>
          <ul class="suggestion-list">
            <li v-for="(s, i) in suggestions.slice(0, 5)" :key="i">
              <el-icon class="sug-icon"><CaretRight /></el-icon>
              <span>{{ typeof s === 'string' ? s : s.title || s.text || '' }}</span>
            </li>
          </ul>
        </el-card>

        <el-card shadow="never">
          <template #header>
            <div class="card-head">
              <el-icon class="head-icon"><TrendCharts /></el-icon>
              <span>最新商机</span>
            </div>
          </template>
          <el-table v-if="opportunities.length" :data="opportunities" size="small" :show-header="false">
            <el-table-column prop="title" min-width="220" show-overflow-tooltip class-name="cell-strong" />
            <el-table-column width="110" align="right">
              <template #default="{ row }">
                <el-tag size="small" effect="light">{{ row.stage || '-' }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无商机" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { Lightning, Warning, AlarmClock, MagicStick, CaretRight, TrendCharts, Refresh } from '@element-plus/icons-vue'
import StatCard from '../components/StatCard.vue'
import { get, getList, post } from '../api'
import { useDictStore, useCrawlStore } from '../stores/app'

const dict = useDictStore()
const crawl = useCrawlStore()
const data = ref({})
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
.card-head { display: flex; align-items: center; gap: 8px; }
.head-icon { color: var(--el-color-primary); }
.head-icon--danger { color: var(--el-color-danger); }
.head-tag { margin-left: auto; }

.item-title { font-weight: 500; color: var(--el-text-color-primary); line-height: 1.5; }
.meta-line { margin-top: 8px; }
.contact-name { color: var(--el-color-primary); font-weight: 500; }

.suggestions-card { border-left: 3px solid var(--el-color-primary); }
.suggestion-list { margin: 0; padding: 0; list-style: none; }
.suggestion-list li {
  display: flex; gap: 6px; align-items: flex-start;
  font-size: 13px; line-height: 1.7; margin-bottom: 8px;
  color: var(--el-text-color-regular);
}
.suggestion-list li:last-child { margin-bottom: 0; }
.sug-icon { color: var(--el-color-primary); margin-top: 4px; flex-shrink: 0; }
</style>
