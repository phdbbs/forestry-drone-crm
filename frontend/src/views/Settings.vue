<template>
  <div class="page">
    <div class="page-header"><h2 class="page-title">系统设置</h2></div>

    <el-card shadow="never">
      <el-tabs v-model="tab">
        <!-- ------------------------------ AI 配置 ------------------------------ -->
        <el-tab-pane label="AI 配置" name="ai">
          <el-form ref="aiFormRef" :model="ai" :rules="aiRules" label-width="120px" class="form-narrow">
            <el-form-item label="API Endpoint" prop="endpoint">
              <el-input v-model="ai.endpoint" placeholder="https://api.openai.com/v1" />
            </el-form-item>
            <el-form-item label="API Key" prop="key">
              <el-input v-model="ai.key" type="password" show-password placeholder="留空表示不修改" />
            </el-form-item>
            <el-form-item label="模型" prop="model">
              <el-input v-model="ai.model" placeholder="如 deepseek-v4-flash" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="aiSaving" @click="saveAI">保存配置</el-button>
              <el-button :loading="aiTesting" @click="testAI">测试连接</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- ------------------------------ 采集配置 ------------------------------ -->
        <el-tab-pane label="采集配置" name="crawl">
          <el-form ref="crawlFormRef" :model="crawlForm" :rules="crawlRules" label-width="120px" class="form-narrow">
            <el-form-item label="采集来源" prop="sources">
              <el-input v-model="crawlForm.sources" type="textarea" :rows="6" placeholder="每行一条，格式：名称|URL" />
            </el-form-item>
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="每次抽取上限">
                  <el-input-number v-model="crawlForm.limit" :min="1" :max="50" controls-position="right" class="w-full" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="上次采集">
                  <el-input v-model="crawlForm.lastAt" readonly />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="关键词过滤">
              <el-checkbox v-model="crawlForm.kwFilter">启用关键词过滤（命中少时自动扩大范围）</el-checkbox>
            </el-form-item>
            <el-form-item label="关键词">
              <el-input v-model="crawlForm.keywords" placeholder="逗号分隔，如：无人机,林业,病虫害" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="crawlSaving" @click="saveCrawl">保存采集配置</el-button>
              <el-button :icon="Lightning" :loading="crawl.running" @click="doCrawl">立即采集</el-button>
              <el-button :icon="Document" @click="tab = 'logs'">查看采集日志</el-button>
            </el-form-item>
          </el-form>
          <el-alert
            v-if="crawl.running"
            type="info"
            :closable="false"
            show-icon
            :title="`采集进行中: ${crawl.phase} ${crawl.progress}/${crawl.total || '-'} ${crawl.current} 已生成 ${crawl.count} 条`"
          />
          <template v-else-if="crawl.message">
            <el-alert type="success" :closable="false" show-icon :title="`上次: ${crawl.message}`" />
            <div v-if="crawl.errors.length" class="run-errors">
              <div class="run-errors-title">本次异常（已按类型识别）：</div>
              <el-tag
                v-for="(e, i) in crawl.errors"
                :key="i"
                size="small"
                type="danger"
                effect="light"
                class="err-chip"
              >{{ e }}</el-tag>
            </div>
          </template>
        </el-tab-pane>

        <!-- ------------------------------ 采集日志 ------------------------------ -->
        <el-tab-pane :label="logTabLabel" name="logs">
          <!-- 概览 -->
          <el-row :gutter="12" class="stat-row">
            <el-col :xs="12" :sm="6">
              <div class="mini-card">
                <div class="mini-label">采集任务</div>
                <div class="mini-value">{{ logStats.total }}</div>
              </div>
            </el-col>
            <el-col :xs="12" :sm="6">
              <div class="mini-card">
                <div class="mini-label">新增数据</div>
                <div class="mini-value ok">{{ logStats.items_total }}</div>
              </div>
            </el-col>
            <el-col :xs="12" :sm="6">
              <div class="mini-card">
                <div class="mini-label">异常总数</div>
                <div class="mini-value bad">{{ logStats.error_total }}</div>
              </div>
            </el-col>
            <el-col :xs="12" :sm="6">
              <div class="mini-card">
                <div class="mini-label">成功率</div>
                <div class="mini-value">{{ successRate }}</div>
              </div>
            </el-col>
          </el-row>

          <!-- 状态分布 -->
          <div class="chip-bar">
            <span class="bar-label">状态：</span>
            <el-tag
              v-for="s in STATUS_LIST"
              :key="s.value"
              size="small"
              :type="s.tag"
              :effect="filters.status === s.value ? 'dark' : 'plain'"
              class="chip"
              @click="filters.status = filters.status === s.value ? 'all' : s.value; loadLogs()"
            >{{ s.label }} {{ logStats.by_status[s.value] || 0 }}</el-tag>
          </div>

          <!-- 错误类型分布 -->
          <div v-if="logStats.error_types.length" class="chip-bar">
            <span class="bar-label">报错类型：</span>
            <el-tooltip
              v-for="t in logStats.error_types"
              :key="t.code"
              :content="typeHint(t.code)"
              placement="top"
            >
              <el-tag
                size="small"
                :type="sevTag(t.severity)"
                :effect="filters.error_code === t.code ? 'dark' : 'plain'"
                class="chip"
                @click="filters.error_code = filters.error_code === t.code ? 'all' : t.code; loadLogs()"
              >{{ t.label }} × {{ t.count }}</el-tag>
            </el-tooltip>
          </div>

          <!-- 筛选 -->
          <div class="log-filters">
            <el-select v-model="filters.task_type" size="small" class="f-select" @change="loadLogs">
              <el-option label="全部任务" value="all" />
              <el-option v-for="t in taskTypes" :key="t" :label="t" :value="t" />
            </el-select>
            <el-select v-model="filters.status" size="small" class="f-select" @change="loadLogs">
              <el-option label="全部状态" value="all" />
              <el-option v-for="s in STATUS_LIST" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
            <el-select v-model="filters.error_code" size="small" class="f-select wide" @change="loadLogs">
              <el-option label="全部报错类型" value="all" />
              <el-option-group v-for="g in errorTypeGroups" :key="g.category" :label="g.category">
                <el-option v-for="t in g.items" :key="t.code" :label="t.label" :value="t.code" />
              </el-option-group>
            </el-select>
            <el-select v-model="filters.days" size="small" class="f-select" @change="loadLogs">
              <el-option label="全部时间" value="all" />
              <el-option label="今天" value="today" />
              <el-option label="近 7 天" value="7" />
              <el-option label="近 30 天" value="30" />
            </el-select>
            <el-input
              v-model="filters.q"
              size="small"
              class="f-search"
              placeholder="搜索关键词 / 来源 / 结果信息"
              clearable
              @keyup.enter="loadLogs"
              @clear="loadLogs"
            />
            <el-button size="small" :icon="Search" @click="loadLogs">查询</el-button>
            <el-button size="small" @click="resetFilters">重置</el-button>
            <div class="grow" />
            <el-button size="small" :icon="Refresh" @click="loadLogs">刷新</el-button>
            <el-button size="small" type="danger" plain :icon="Delete" @click="clearLogs">清理日志</el-button>
          </div>

          <!-- 日志表 -->
          <el-table
            v-loading="logsLoading"
            :data="logs"
            size="small"
            row-key="id"
            empty-text="暂无采集日志，可在「采集配置」中点击「立即采集」"
            @expand-change="onExpand"
          >
            <el-table-column type="expand">
              <template #default="{ row }">
                <div class="detail-wrap">
                  <div v-if="!row._detail" class="muted">加载明细中…</div>
                  <template v-else-if="row._detail.length">
                    <div class="detail-head">本次异常明细（{{ row._detail.length }}）</div>
                    <el-table :data="row._detail" size="small" border class="detail-table">
                      <el-table-column label="报错类型" width="140">
                        <template #default="{ row: d }">
                          <el-tag size="small" :type="sevTag(d.severity)">{{ d.label }}</el-tag>
                        </template>
                      </el-table-column>
                      <el-table-column prop="stage" label="阶段" width="110" />
                      <el-table-column prop="target" label="对象" min-width="160" show-overflow-tooltip />
                      <el-table-column prop="raw" label="原始报错" min-width="280" show-overflow-tooltip />
                      <el-table-column prop="hint" label="处理建议" min-width="260" show-overflow-tooltip />
                    </el-table>
                  </template>
                  <div v-else class="muted">本次采集无异常。</div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="开始时间" width="150">
              <template #default="{ row }">{{ fmtTime(row.started_at) }}</template>
            </el-table-column>
            <el-table-column prop="task_type" label="任务类型" width="110" show-overflow-tooltip />
            <el-table-column label="状态" width="96" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="statusTag(row.status)">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="采集内容" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">{{ row.keywords || row.sources || '—' }}</template>
            </el-table-column>
            <el-table-column label="结果信息" min-width="260" show-overflow-tooltip>
              <template #default="{ row }">{{ row.message || '—' }}</template>
            </el-table-column>
            <el-table-column label="新增" width="72" align="center">
              <template #default="{ row }">
                <span :class="{ ok: row.items_count > 0 }">{{ row.items_count }}</span>
              </template>
            </el-table-column>
            <el-table-column label="异常" width="200">
              <template #default="{ row }">
                <template v-if="row.error_types && row.error_types.length">
                  <el-tooltip
                    v-for="t in row.error_types.slice(0, 2)"
                    :key="t.code"
                    :content="typeHint(t.code)"
                    placement="top"
                  >
                    <el-tag size="small" :type="sevTag(t.severity)" class="chip-sm">{{ t.label }} {{ t.count }}</el-tag>
                  </el-tooltip>
                  <span v-if="row.error_types.length > 2" class="muted">+{{ row.error_types.length - 2 }}</span>
                </template>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
            <el-table-column label="耗时" width="80" align="right">
              <template #default="{ row }">{{ fmtDuration(row.duration_ms) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="72" align="center" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-if="logTotal > 0"
            class="pager"
            size="small"
            layout="total, sizes, prev, pager, next"
            :total="logTotal"
            :current-page="page"
            :page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            @current-change="(p) => { page = p; loadLogs() }"
            @size-change="(s) => { pageSize = s; page = 1; loadLogs() }"
          />
        </el-tab-pane>

        <!-- ------------------------------ 技能管理 ------------------------------ -->
        <el-tab-pane :label="`技能管理${skills.length ? ' (' + skills.length + ')' : ''}`" name="skills">
          <el-table v-loading="skillsLoading" :data="skills" size="default" empty-text="暂无技能">
            <el-table-column label="技能" min-width="200">
              <template #default="{ row }">
                <div class="skill-cell">
                  <el-icon class="skill-icon"><Tools /></el-icon>
                  <span class="skill-name">{{ row.name }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="说明" min-width="280" show-overflow-tooltip />
            <el-table-column label="状态" width="90" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.is_builtin || row.is_active ? 'success' : 'info'">
                  {{ row.is_builtin ? '内置' : row.is_active ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" align="center">
              <template #default="{ row }">
                <el-button v-if="!row.is_builtin" link type="danger" size="small" @click="deleteSkill(row.id)">删除</el-button>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- ------------------------------ 新闻采集 ------------------------------ -->
        <el-tab-pane label="新闻采集" name="news">
          <el-form label-width="120px" class="form-narrow">
            <el-form-item label="新闻来源">
              <el-input v-model="newsSources" type="textarea" :rows="4" placeholder="每行一条，格式：名称|URL" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="newsSaving" @click="saveNews">保存新闻来源</el-button>
              <el-button :loading="batchLoading" @click="batchCollect">批量采集客户新闻 + 联系人动态</el-button>
            </el-form-item>
          </el-form>
          <el-alert type="info" :closable="false" show-icon
            title="新闻采集的运行记录已并入「采集日志」标签页，可按任务类型「客户新闻 / 联系人动态」筛选。">
            <el-button link type="primary" @click="filters.task_type = 'all'; tab = 'logs'">前往采集日志 →</el-button>
          </el-alert>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 日志详情抽屉 -->
    <el-drawer v-model="drawer" title="采集日志详情" size="720px" direction="rtl">
      <div v-if="detail" class="drawer-body">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="任务类型">{{ detail.task_type || '—' }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag size="small" :type="statusTag(detail.status)">{{ statusLabel(detail.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ fmtTime(detail.started_at) }}</el-descriptions-item>
          <el-descriptions-item label="结束时间">{{ fmtTime(detail.finished_at) }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ fmtDuration(detail.duration_ms) }}</el-descriptions-item>
          <el-descriptions-item label="新增 / 异常">
            <span class="ok">{{ detail.items_count }}</span> / <span class="bad">{{ detail.error_count }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="搜索范围" :span="2">
            {{ detail.range_start || '—' }} ~ {{ detail.range_end || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="关键词" :span="2">{{ detail.keywords || '—' }}</el-descriptions-item>
          <el-descriptions-item label="来源" :span="2">{{ detail.sources || '—' }}</el-descriptions-item>
          <el-descriptions-item label="结果信息" :span="2">{{ detail.message || '—' }}</el-descriptions-item>
        </el-descriptions>

        <div class="detail-head">报错分类汇总</div>
        <div v-if="detail.error_types && detail.error_types.length" class="chip-bar">
          <el-tag v-for="t in detail.error_types" :key="t.code" size="small" :type="sevTag(t.severity)">
            {{ t.label }} × {{ t.count }}
          </el-tag>
        </div>
        <div v-else class="muted">本次采集未产生异常。</div>

        <div class="detail-head">异常明细（{{ (detail.error_detail || []).length }}）</div>
        <el-table :data="detail.error_detail || []" size="small" border empty-text="无">
          <el-table-column label="报错类型" width="130">
            <template #default="{ row }">
              <el-tag size="small" :type="sevTag(row.severity)">{{ row.label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="stage" label="阶段" width="100" />
          <el-table-column prop="target" label="对象" min-width="140" show-overflow-tooltip />
          <el-table-column prop="raw" label="原始报错" min-width="240" show-overflow-tooltip />
          <el-table-column prop="hint" label="处理建议" min-width="240" show-overflow-tooltip />
        </el-table>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Lightning, Tools, Document, Refresh, Search, Delete } from '@element-plus/icons-vue'
import { get, getList, post, put, del } from '../api'
import { useCrawlStore } from '../stores/app'

const crawl = useCrawlStore()
const tab = ref('ai')

const STATUS_LIST = [
  { value: 'running', label: '进行中', tag: 'info' },
  { value: 'success', label: '成功', tag: 'success' },
  { value: 'partial', label: '部分异常', tag: 'warning' },
  { value: 'failed', label: '失败', tag: 'danger' },
  { value: 'interrupted', label: '已中断', tag: 'info' },
]

const ai = reactive({ endpoint: '', key: '', model: '' })
const aiFormRef = ref(null)
const aiSaving = ref(false)
const aiTesting = ref(false)
const aiRules = {
  endpoint: [{ required: true, message: '请输入 API Endpoint', trigger: 'blur' }],
  model: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
}

const crawlForm = reactive({ sources: '', limit: 5, lastAt: '', kwFilter: true, keywords: '' })
const crawlFormRef = ref(null)
const crawlSaving = ref(false)
const crawlRules = {
  sources: [{ required: true, message: '请至少填写一条采集来源', trigger: 'blur' }],
}

const newsSources = ref('')
const newsSaving = ref(false)
const skills = ref([])
const skillsLoading = ref(false)
const batchLoading = ref(false)

// ------------------------------ 采集日志 ------------------------------
const logs = ref([])
const logsLoading = ref(false)
const logTotal = ref(0)
const page = ref(1)
const pageSize = ref(20)
const taskTypes = ref([])
const errorTypes = ref([])
const detail = ref(null)
const drawer = ref(false)
// 默认看全部时间：采集不是每天都有，默认收窄窗口会让页面看起来"没有日志"
const filters = reactive({ task_type: 'all', status: 'all', error_code: 'all', days: 'all', q: '' })
const logStats = reactive({ total: 0, items_total: 0, error_total: 0, by_status: {}, error_types: [] })

const logTabLabel = computed(() => (logStats.total ? `采集日志 (${logStats.total})` : '采集日志'))

const successRate = computed(() => {
  const st = logStats.by_status || {}
  const ok = (st.success || 0) + (st.partial || 0)
  const all = logStats.total || 0
  return all ? Math.round((ok / all) * 100) + '%' : '—'
})

// 报错类型字典按大类分组，供筛选下拉使用
const errorTypeGroups = computed(() => {
  const groups = {}
  for (const t of errorTypes.value) {
    (groups[t.category] = groups[t.category] || []).push(t)
  }
  return Object.entries(groups).map(([category, items]) => ({ category, items }))
})

const typeHint = (code) => errorTypes.value.find((t) => t.code === code)?.hint || ''

const statusLabel = (s) => STATUS_LIST.find((x) => x.value === s)?.label || s || '—'
const statusTag = (s) => STATUS_LIST.find((x) => x.value === s)?.tag || 'info'
const sevTag = (sev) => (sev === 'error' ? 'danger' : sev === 'warning' ? 'warning' : 'info')

const fmtTime = (d) => (d ? String(d).substring(0, 19) : '—')
const fmtDuration = (ms) => {
  const n = Number(ms) || 0
  if (!n) return '—'
  return n < 1000 ? `${n}ms` : `${(n / 1000).toFixed(1)}s`
}

const parseSources = (v) => (v || '').split('\n').map((s) => s.trim()).filter(Boolean).map((l) => {
  const sep = l.indexOf('|')
  if (sep > 0) return { name: l.slice(0, sep).trim(), url: l.slice(sep + 1).trim(), enabled: true }
  return { name: l, url: l, enabled: true }
})
const sourcesToText = (cfg, key) => {
  let sources = []
  try { sources = JSON.parse(cfg[key]?.value || '[]') } catch (e) {}
  if (Array.isArray(sources) && sources.length) {
    return sources.filter((s) => s && s.url).map((s) => `${s.name || s.url}|${s.url}`).join('\n')
  }
  return ''
}

async function saveAI() {
  if (!aiFormRef.value) return
  const valid = await aiFormRef.value.validate().catch(() => false)
  if (!valid) return
  aiSaving.value = true
  try {
    const r = await put('/config', { ai_api_endpoint: ai.endpoint, ai_api_key: ai.key, ai_model: ai.model })
    if (r.error) return ElMessage.error(r.error)
    ElMessage.success('AI 配置已保存')
  } finally {
    aiSaving.value = false
  }
}

async function testAI() {
  aiTesting.value = true
  try {
    const r = await post('/config/test-ai')
    if (r.ok) return ElMessage.success(r.message || '连接正常')
    // 报错已按类型归类：直接展示「模型额度不足 / 鉴权失败…」及处理建议
    ElMessage.error(r.label ? `${r.label}：${r.hint || r.error}` : (r.error || '连接失败'))
  } finally {
    aiTesting.value = false
  }
}

async function saveCrawl() {
  if (!crawlFormRef.value) return
  const valid = await crawlFormRef.value.validate().catch(() => false)
  if (!valid) return
  crawlSaving.value = true
  try {
    const r = await put('/config', {
      keywords: crawlForm.keywords,
      crawl_sources: JSON.stringify(parseSources(crawlForm.sources)),
      crawl_limit: String(crawlForm.limit || 5),
      crawl_keyword_filter: crawlForm.kwFilter ? '1' : '0',
    })
    if (r.error) return ElMessage.error(r.error)
    ElMessage.success('采集配置已保存')
  } finally {
    crawlSaving.value = false
  }
}

async function doCrawl() {
  const msg = await crawl.start()
  msg ? ElMessage.error(msg) : ElMessage.info('采集已启动，正在抓取并 AI 分析...')
}

async function saveNews() {
  newsSaving.value = true
  try {
    const r = await put('/config', { news_sources: JSON.stringify(parseSources(newsSources.value)) })
    if (r.error) return ElMessage.error(r.error)
    ElMessage.success('新闻来源已保存')
  } finally {
    newsSaving.value = false
  }
}

async function batchCollect() {
  batchLoading.value = true
  try {
    const r = await post('/news/collect-all', { type: 'all' })
    if (r.error) { ElMessage.error(r.error); return }
    const suffix = r.errors?.length ? `（${r.errors.length} 个异常）` : ''
    ElMessage.success((r.message || '采集完成') + suffix)
    loadLogs()
  } finally {
    batchLoading.value = false
  }
}

async function loadLogs() {
  logsLoading.value = true
  try {
    const qs = new URLSearchParams({
      page: String(page.value), page_size: String(pageSize.value),
      task_type: filters.task_type, status: filters.status,
      error_code: filters.error_code, days: filters.days,
    })
    if (filters.q) qs.set('q', filters.q)
    const r = await get('/crawl/logs?' + qs.toString())
    if (r.error) { ElMessage.error(r.error); return }
    logs.value = r.items || []
    logTotal.value = r.total || 0
    taskTypes.value = r.task_types || []
    Object.assign(logStats, r.stats || {})
  } finally {
    logsLoading.value = false
  }
}

async function loadErrorTypes() {
  errorTypes.value = await getList('/error-types')
}

function resetFilters() {
  Object.assign(filters, { task_type: 'all', status: 'all', error_code: 'all', days: 'all', q: '' })
  page.value = 1
  loadLogs()
}

// 展开行时才拉取明细，避免列表接口返回大字段
async function onExpand(row, expanded) {
  const isOpen = Array.isArray(expanded) ? expanded.some((r) => r.id === row.id) : !!expanded
  if (!isOpen || row._detail) return
  const r = await get(`/crawl/logs/${row.id}`)
  row._detail = r.error_detail || []
}

async function openDetail(row) {
  const r = await get(`/crawl/logs/${row.id}`)
  if (r.error) return ElMessage.error(r.error)
  detail.value = r
  drawer.value = true
}

async function clearLogs() {
  try {
    await ElMessageBox.confirm(
      '将删除所选时间范围内的采集日志记录（不影响已采集的线索/客户数据）。是否继续？',
      '清理采集日志', { type: 'warning', confirmButtonText: '删除全部', cancelButtonText: '取消' },
    )
  } catch (e) { return }
  const r = await del('/crawl/logs?days=all')
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success(r.message || '已清理')
  page.value = 1
  loadLogs()
}

async function loadSkills() {
  skillsLoading.value = true
  const data = await get('/skills')
  skills.value = [
    ...((data.builtin || []).map((s) => ({ ...s, is_builtin: true }))),
    ...(data.custom || []),
  ]
  skillsLoading.value = false
}

async function deleteSkill(id) {
  try {
    await ElMessageBox.confirm('确认删除该技能？', '删除技能', { type: 'warning' })
  } catch (e) { return }
  const r = await del(`/skills/${id}`)
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success('已删除')
  loadSkills()
}

onMounted(async () => {
  const config = await get('/config')
  const getV = (k, d = '') => config[k]?.value || d
  ai.endpoint = getV('ai_api_endpoint', 'https://api.openai.com/v1')
  ai.key = getV('ai_api_key', '')
  ai.model = getV('ai_model', 'gpt-4o')
  crawlForm.sources = sourcesToText(config, 'crawl_sources')
  crawlForm.lastAt = config.last_crawl_at?.value || '首次采集（自动回溯最近 7 天）'
  crawlForm.limit = Number(config.crawl_limit?.value || 5) || 5
  crawlForm.kwFilter = (config.crawl_keyword_filter?.value || '1') !== '0'
  crawlForm.keywords = getV('keywords', '无人机,林业,病虫害,巡检')
  newsSources.value = sourcesToText(config, 'news_sources')
  await nextTick()
  aiFormRef.value?.clearValidate()
  crawlFormRef.value?.clearValidate()
  loadSkills()
  loadErrorTypes()
  loadLogs()
  crawl.checkRunning()
})

// 采集结束后自动刷新日志
watch(() => crawl.finishedAt, () => {
  if (crawl.finishedAt) { page.value = 1; loadLogs() }
})
</script>

<style scoped>
.form-narrow { max-width: 620px; }
.w-full { width: 100%; }
.skill-cell { display: flex; align-items: center; gap: 8px; }
.skill-icon { color: var(--el-color-primary); }
.skill-name { font-weight: 500; }

.run-errors { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.run-errors-title { font-size: 13px; color: var(--el-text-color-secondary); margin-right: 4px; }
.err-chip { max-width: 100%; }

.stat-row { margin-bottom: 14px; }
.mini-card {
  background: var(--el-fill-color-blank);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  padding: 10px 14px;
}
.mini-label { font-size: 12px; color: var(--el-text-color-secondary); }
.mini-value { font-size: 22px; font-weight: 600; margin-top: 2px; }
.mini-value.ok { color: var(--el-color-success); }
.mini-value.bad { color: var(--el-color-danger); }

.chip-bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 10px; }
.bar-label { font-size: 13px; color: var(--el-text-color-secondary); }
.chip { cursor: pointer; }
.chip-sm { margin-right: 4px; }

.log-filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 6px 0 12px; }
.f-select { width: 128px; }
.f-select.wide { width: 168px; }
.f-search { width: 220px; }
.grow { flex: 1; }

.detail-wrap { padding: 8px 12px 12px; }
.detail-head { font-size: 13px; font-weight: 600; margin: 14px 0 8px; }
.detail-table { margin-bottom: 4px; }
.pager { margin-top: 12px; justify-content: flex-end; }
.drawer-body { padding-bottom: 20px; }

.ok { color: var(--el-color-success); }
.bad { color: var(--el-color-danger); }
.muted { color: var(--el-text-color-secondary); font-size: 13px; }
</style>
