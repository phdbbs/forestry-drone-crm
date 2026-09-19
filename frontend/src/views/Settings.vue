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
            </el-form-item>
          </el-form>
          <el-alert
            v-if="crawl.running"
            type="info"
            :closable="false"
            show-icon
            :title="`采集进行中: ${crawl.phase} ${crawl.progress}/${crawl.total || '-'} ${crawl.current} 已生成 ${crawl.count} 条`"
          />
          <el-alert
            v-else-if="crawl.message"
            type="success"
            :closable="false"
            show-icon
            :title="`上次: ${crawl.message}${crawl.errors.length ? ' | ' + crawl.errors.slice(0, 2).join('; ') : ''}`"
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

          <el-divider content-position="left">采集日志</el-divider>
          <el-table v-loading="logsLoading" :data="logs" size="small" max-height="280" empty-text="暂无采集日志">
            <el-table-column label="时间" width="110">
              <template #default="{ row }">{{ fmtDate(row.started_at) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="logTagType(row.status)">{{ logLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="task_type" label="类型" width="140" show-overflow-tooltip />
            <el-table-column label="结果" width="140">
              <template #default="{ row }">
                新增 {{ row.items_count }} 条<template v-if="row.error_count"> / 异常 {{ row.error_count }}</template>
              </template>
            </el-table-column>
            <el-table-column prop="message" label="信息" min-width="240" show-overflow-tooltip />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Lightning, Tools } from '@element-plus/icons-vue'
import { get, getList, post, put, del, fmtDate } from '../api'
import { useCrawlStore } from '../stores/app'

const crawl = useCrawlStore()
const tab = ref('ai')

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
const logs = ref([])
const logsLoading = ref(false)
const batchLoading = ref(false)

const logTagType = (s) => (s === 'success' ? 'success' : s === 'partial' ? 'warning' : 'danger')
const logLabel = (s) => (s === 'success' ? '成功' : s === 'partial' ? '部分异常' : '失败')

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
    r.ok ? ElMessage.success(r.message || '连接正常') : ElMessage.error(r.error || '连接失败')
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
  logs.value = await getList('/news/logs')
  logsLoading.value = false
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
  loadLogs()
  crawl.checkRunning()
})

watch(() => crawl.finishedAt, () => { loadLogs() })
</script>

<style scoped>
.form-narrow { max-width: 620px; }
.w-full { width: 100%; }
.skill-cell { display: flex; align-items: center; gap: 8px; }
.skill-icon { color: var(--el-color-primary); }
.skill-name { font-weight: 500; }
</style>
