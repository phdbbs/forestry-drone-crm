<template>
  <div class="page">
    <el-row :gutter="16" class="card-block">
      <el-col :span="6" v-for="s in statCards" :key="s.label">
        <StatCard :label="s.label" :value="s.value" :icon="s.icon" :color="s.color" :value-color="s.valueColor" />
      </el-col>
    </el-row>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px" class="dash-grid">
      <div>
        <el-card shadow="never" class="card-block">
          <template #header><span style="font-weight:600">🔥 紧急事项</span></template>
          <template v-if="data.urgent_leads?.length">
            <div v-for="l in data.urgent_leads" :key="l.id"
              :style="{ padding: '10px 12px', borderRadius: '8px', marginBottom: '8px', fontSize: '13px', background: levelBg(l.level) }">
              <div style="font-weight:500">{{ l.title }}</div>
              <div class="muted" style="margin-top:4px">{{ l.customer_name || '' }} | 截止: {{ l.deadline || '-' }}</div>
            </div>
          </template>
          <el-empty v-else description="暂无紧急事项" :image-size="60" />
        </el-card>

        <el-card shadow="never" class="card-block">
          <template #header>
            <div style="display:flex;align-items:center">
              <span style="font-weight:600">⚡ AI 紧急任务 · 当日跟进方案</span>
              <el-button size="small" style="margin-left:auto" :loading="aiLoading" @click="loadTasks(true)">刷新</el-button>
            </div>
          </template>
          <div v-if="aiLoading" class="muted" style="padding:12px 0">AI 分析中，请稍候（首次约 1-2 分钟）...</div>
          <template v-else-if="aiTasks.length">
            <div v-for="(t, i) in aiTasks" :key="i"
              :style="{ padding: '10px 12px', borderRadius: '8px', marginBottom: '8px', fontSize: '13px', background: prioBg(t.priority) }">
              <div style="font-weight:500">{{ t.title }}</div>
              <div class="muted" style="margin-top:4px">{{ t.content }}<template v-if="t.related"><br>关联: {{ t.related }}</template></div>
            </div>
            <div class="muted" style="font-size:11px;margin-top:6px">
              生成: {{ aiMeta.generated_at || '' }}{{ aiMeta.source === 'cache' ? '（缓存，可点刷新）' : '' }}
            </div>
          </template>
          <el-empty v-else :description="aiError || '暂无 AI 跟进任务'" :image-size="60" />
        </el-card>

        <el-card shadow="never">
          <template #header><span style="font-weight:600">⏰ 今日联络计划</span></template>
          <template v-if="data.today_followups?.length">
            <div v-for="f in data.today_followups" :key="f.id" style="padding:8px 0;border-bottom:1px solid #f1f5f9;font-size:13px">
              <span style="color:var(--el-color-primary);font-weight:500">{{ f.contact_name || '' }}</span> - {{ f.content }}
            </div>
          </template>
          <el-empty v-else description="今日无联络计划" :image-size="60" />
        </el-card>
      </div>

      <div>
        <el-card v-if="suggestions.length" shadow="never" class="card-block" style="background:#faf5ff">
          <template #header><span style="font-weight:600;color:#7c3aed">⚡ AI 智能建议</span></template>
          <div v-for="(s, i) in suggestions.slice(0, 4)" :key="i" style="display:flex;gap:8px;font-size:13px;margin-bottom:8px">
            <el-icon color="#8b5cf6" style="flex-shrink:0;margin-top:2px"><Lightning /></el-icon>
            <span>{{ typeof s === 'string' ? s : s.title || s.text || '' }}</span>
          </div>
        </el-card>
        <el-card shadow="never">
          <template #header><span style="font-weight:600">🎯 最新商机</span></template>
          <template v-if="data.opportunities?.length">
            <div v-for="o in data.opportunities.slice(0, 5)" :key="o.id"
              style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f1f5f9;font-size:13px">
              <span>{{ o.title }}</span>
              <el-tag size="small">{{ o.stage }}</el-tag>
            </div>
          </template>
          <el-empty v-else description="暂无商机" :image-size="60" />
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { Lightning } from '@element-plus/icons-vue'
import StatCard from '../components/StatCard.vue'
import { get, post } from '../api'
import { useDictStore, useCrawlStore } from '../stores/app'

const dict = useDictStore()
const crawl = useCrawlStore()
const data = ref({})
const suggestions = ref([])

const statCards = computed(() => {
  const s = data.value.stats || {}
  return [
    { label: '活跃线索', value: s.active_leads ?? 0, icon: 'Aim', color: 'var(--el-color-primary)' },
    { label: '商机总数', value: s.opportunities ?? 0, icon: 'DataAnalysis', color: '#3b82f6' },
    { label: '今日活动', value: s.today_activities ?? 0, icon: 'Phone', color: '#f59e0b' },
    { label: '紧急线索', value: s.urgent_leads ?? 0, icon: 'Lightning', color: '#ef4444', valueColor: '#ef4444' },
  ]
})
const levelBg = (lv) => ({ 高匹配: '#fee2e2', 中匹配: '#fef3c7' }[lv] || '#f1f5f9')
const prioBg = (p) => ({ high: '#fee2e2', medium: '#fef3c7' }[p] || '#f1f5f9')

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
  if (force && r.ok) dict.loadOpportunities()
}

onMounted(async () => {
  const [d, s] = await Promise.all([get('/dashboard'), get('/suggestions').catch(() => [])])
  data.value = d
  suggestions.value = Array.isArray(s) ? s : []
  const total = (d.urgent_leads?.length || 0) + (d.today_followups?.length || 0)
  window.dispatchEvent(new CustomEvent('crm:notif', { detail: total }))
  loadTasks(false)
  crawl.checkRunning()
})
watch(() => crawl.finishedAt, async () => {
  data.value = await get('/dashboard')
})
</script>

<style scoped>
@media (max-width: 1000px) { .dash-grid { grid-template-columns: 1fr !important; } }
</style>
