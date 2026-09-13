<template>
  <div class="page">
    <div class="page-header"><h2 class="page-title">系统设置</h2></div>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="never" class="card-block">
          <template #header><span style="font-weight:600">AI 配置</span></template>
          <el-form label-width="120px">
            <el-form-item label="API Endpoint"><el-input v-model="ai.endpoint" /></el-form-item>
            <el-form-item label="API Key"><el-input v-model="ai.key" type="password" show-password /></el-form-item>
            <el-form-item label="模型"><el-input v-model="ai.model" /></el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveAI">保存配置</el-button>
              <el-button @click="testAI">测试连接</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" class="card-block">
          <template #header><span style="font-weight:600">采集配置（AI 真实采集）</span></template>
          <el-form label-width="190px">
            <el-form-item label="采集来源(每行: 名称|URL)">
              <el-input v-model="crawlForm.sources" type="textarea" :rows="5" />
            </el-form-item>
            <el-row :gutter="12">
              <el-col :span="12"><el-form-item label="每次 AI 抽取上限(条)"><el-input v-model="crawlForm.limit" type="number" :min="1" :max="50" /></el-form-item></el-col>
              <el-col :span="12"><el-form-item label="上次采集时间点"><el-input v-model="crawlForm.lastAt" readonly /></el-form-item></el-col>
            </el-row>
            <el-form-item label="关键词过滤">
              <el-checkbox v-model="crawlForm.kwFilter">启用关键词过滤（命中少时自动扩大范围）</el-checkbox>
            </el-form-item>
            <el-form-item label="关键词(逗号分隔)"><el-input v-model="crawlForm.keywords" /></el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveCrawl">保存采集配置</el-button>
              <el-button :loading="crawl.running" @click="doCrawl"><el-icon><Lightning /></el-icon>&nbsp;立即采集</el-button>
            </el-form-item>
          </el-form>
          <el-alert v-if="crawl.running" type="info" :closable="false"
            :title="`采集进行中: ${crawl.phase} ${crawl.progress}/${crawl.total || '-'} ${crawl.current} 已生成 ${crawl.count} 条`" />
          <el-alert v-else-if="crawl.message" type="success" :closable="false" :title="`上次: ${crawl.message}${crawl.errors.length ? ' | ' + crawl.errors.slice(0, 2).join('; ') : ''}`" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="card-block">
      <template #header><span style="font-weight:600">技能管理</span></template>
      <div v-for="s in skills" :key="s.id" style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f1f5f9">
        <div>
          <el-tag size="small" style="margin-right:8px">{{ s.icon || '🔧' }} {{ s.name }}</el-tag>
          <span class="muted">{{ s.description }}</span>
        </div>
        <div style="display:flex;gap:6px;align-items:center">
          <el-tag size="small" :type="s.is_builtin || s.is_active ? 'success' : 'info'">{{ s.is_builtin ? '内置' : s.is_active ? '启用' : '禁用' }}</el-tag>
          <el-button v-if="!s.is_builtin" link type="danger" size="small" @click="deleteSkill(s.id)"><el-icon><Delete /></el-icon></el-button>
        </div>
      </div>
      <el-empty v-if="!skills.length" description="暂无技能" :image-size="60" />
    </el-card>

    <el-card shadow="never">
      <template #header><span style="font-weight:600">⚡ 新闻/动态采集</span></template>
      <el-form label-width="190px">
        <el-form-item label="新闻来源(每行: 名称|URL)">
          <el-input v-model="newsSources" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveNews">保存新闻来源</el-button>
          <el-button :loading="batchLoading" @click="batchCollect">批量采集客户新闻+联系人动态</el-button>
          <span v-if="batchMsg" class="muted" style="margin-left:8px">{{ batchMsg }}</span>
        </el-form-item>
      </el-form>
      <div style="font-weight:600;font-size:13px;margin:8px 0">采集日志</div>
      <div style="max-height:220px;overflow-y:auto;font-size:12px">
        <div v-for="l in logs" :key="l.id" style="display:flex;gap:8px;align-items:center;padding:5px 0;border-bottom:1px solid #f1f5f9">
          <span class="muted">{{ fmtDate(l.started_at) }}</span>
          <el-tag size="small" :type="l.status === 'success' ? 'success' : l.status === 'partial' ? 'warning' : 'danger'">
            {{ l.status === 'success' ? '成功' : l.status === 'partial' ? '部分异常' : '失败' }}
          </el-tag>
          <span>{{ l.task_type }}</span>
          <span class="muted">新增 {{ l.items_count }} 条{{ l.error_count ? ` / 异常 ${l.error_count}` : '' }}</span>
          <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" class="muted">{{ l.message }}</span>
        </div>
        <el-empty v-if="!logs.length" description="暂无采集日志" :image-size="60" />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Lightning, Delete } from '@element-plus/icons-vue'
import { get, post, put, del, fmtDate } from '../api'
import { useCrawlStore } from '../stores/app'

const crawl = useCrawlStore()
const ai = reactive({ endpoint: '', key: '', model: '' })
const crawlForm = reactive({ sources: '', limit: '5', lastAt: '', kwFilter: true, keywords: '' })
const newsSources = ref('')
const skills = ref([])
const logs = ref([])
const batchLoading = ref(false)
const batchMsg = ref('')

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
  await put('/config', { ai_api_endpoint: ai.endpoint, ai_api_key: ai.key, ai_model: ai.model })
  ElMessage.success('AI配置已保存')
}
async function testAI() {
  ElMessage.info('测试中...')
  const r = await post('/config/test-ai')
  r.ok ? ElMessage.success(r.message) : ElMessage.error(r.error || '连接失败')
}
async function saveCrawl() {
  await put('/config', {
    keywords: crawlForm.keywords,
    crawl_sources: JSON.stringify(parseSources(crawlForm.sources)),
    crawl_limit: crawlForm.limit || '5',
    crawl_keyword_filter: crawlForm.kwFilter ? '1' : '0',
  })
  ElMessage.success('采集配置已保存')
}
async function doCrawl() {
  const msg = await crawl.start()
  msg ? ElMessage.error(msg) : ElMessage.info('采集已启动，正在抓取并AI分析...')
}
async function saveNews() {
  await put('/config', { news_sources: JSON.stringify(parseSources(newsSources.value)) })
  ElMessage.success('新闻来源已保存')
}
async function batchCollect() {
  batchLoading.value = true
  batchMsg.value = '采集中，请稍候（按客户/联系人逐条抓取）...'
  const r = await post('/news/collect-all', { type: 'all' })
  batchLoading.value = false
  ElMessage(r.message || '完成')
  batchMsg.value = (r.message || '') + (r.errors?.length ? `（${r.errors.length} 个异常）` : '')
  loadLogs()
}
async function loadLogs() { logs.value = (await get('/news/logs')) || [] }
async function deleteSkill(id) {
  await ElMessageBox.confirm('确认删除该技能？', '删除技能')
  await del(`/skills/${id}`)
  ElMessage.success('已删除')
  loadSkills()
}
async function loadSkills() {
  const data = await get('/skills')
  skills.value = [...(data.builtin || []).map((s) => ({ ...s, is_builtin: true })), ...(data.custom || [])]
}

onMounted(async () => {
  const config = await get('/config')
  const getV = (k, d = '') => config[k]?.value || d
  ai.endpoint = getV('ai_api_endpoint', 'https://api.openai.com/v1')
  ai.key = getV('ai_api_key', '')
  ai.model = getV('ai_model', 'gpt-4o')
  crawlForm.sources = sourcesToText(config, 'crawl_sources')
  crawlForm.lastAt = config.last_crawl_at?.value || '首次采集（自动回溯最近7天）'
  crawlForm.limit = config.crawl_limit?.value || '5'
  crawlForm.kwFilter = (config.crawl_keyword_filter?.value || '1') !== '0'
  crawlForm.keywords = getV('keywords', '无人机,林业,病虫害,巡检')
  newsSources.value = sourcesToText(config, 'news_sources')
  loadSkills()
  loadLogs()
  crawl.checkRunning()
})
watch(() => crawl.finishedAt, () => { loadLogs() })
</script>
