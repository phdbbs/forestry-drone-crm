<template>
  <div class="page">
    <PageHeader title="系统设置" subtitle="AI 服务、采集任务、日志与技能的一站式配置" />

    <div class="settings-card">
      <el-tabs v-model="tab">
        <!-- ------------------------------ AI 配置 ------------------------------ -->
        <el-tab-pane label="AI 配置" name="ai">
          <div class="tab-body">
            <div class="ai-toolbar">
              <div class="note-box note-box--inline">
                列表顺序即「轮换 + 故障切换」次序：调用时轮流从不同服务起步以分摊各家额度；某家<b>鉴权失败 / 额度不足 / 连不上 / 不可用</b>时自动切到下一家，全部失败才报错。增删改后需点「保存配置」写入后端。
              </div>
              <div class="ai-toolbar-actions">
                <el-button :icon="Plus" @click="openProviderForm()">添加一家</el-button>
                <el-button type="primary" :loading="aiSaving" @click="saveProviders">保存配置</el-button>
              </div>
            </div>

            <div class="table-wrap">
              <PageTable
                storage-key="ai_providers" :data="providers" :reorderable="false" :show-footer="false"
                empty-text="还没有配置模型服务" empty-hint="点「添加一家」接入第一个模型，可再加多家做轮换容错"
              >
                <template #empty-action>
                  <el-button type="primary" plain size="small" :icon="Plus" @click="openProviderForm()" style="margin-top:12px">添加一家</el-button>
                </template>

                <el-table-column label="编号" width="76" align="center">
                  <template #default="{ $index }"><span class="mono serial">{{ String($index + 1).padStart(2, '0') }}</span></template>
                </el-table-column>
                <el-table-column prop="name" label="名称" min-width="150" show-overflow-tooltip>
                  <template #default="{ row }">
                    <span v-if="row.name">{{ row.name }}</span>
                    <span v-else class="dim">未命名</span>
                    <span v-if="row.enabled === false" class="dim"> · 已停用</span>
                  </template>
                </el-table-column>
                <el-table-column prop="endpoint" label="Endpoint" min-width="250" show-overflow-tooltip>
                  <template #default="{ row }"><span class="mono dim">{{ row.endpoint || '—' }}</span></template>
                </el-table-column>
                <el-table-column label="API Key" min-width="130">
                  <template #default="{ row }">
                    <span v-if="row.has_key" class="mono">{{ row.key_masked }}</span>
                    <span v-else class="is-bad">未配置</span>
                  </template>
                </el-table-column>
                <el-table-column prop="model" label="模型名称" min-width="150" show-overflow-tooltip>
                  <template #default="{ row }"><span class="mono">{{ row.model || '—' }}</span></template>
                </el-table-column>
                <el-table-column label="操作" width="168" fixed="right" align="right">
                  <template #default="{ row, $index }">
                    <div class="row-actions">
                      <el-button link size="small" :loading="row.verifying" @click="verifyRow($index)">验证</el-button>
                      <el-button link size="small" @click="openProviderForm($index)">修改</el-button>
                      <el-button link type="danger" size="small" @click="removeProvider($index)">删除</el-button>
                    </div>
                  </template>
                </el-table-column>
              </PageTable>
            </div>

            <div class="ai-count muted">共 {{ providers.length }} 家，已启用 {{ enabledCount }} 家</div>

            <!-- 添加 / 修改 模型服务 -->
            <el-dialog v-model="providerFormVisible" :title="providerEditIndex === null ? '添加模型服务' : '修改模型服务'" width="580px" destroy-on-close>
              <el-form label-width="104px">
                <el-form-item label="服务名称">
                  <el-input v-model="pform.name" placeholder="如 深度求索 / 本地 Qwen" />
                </el-form-item>
                <el-form-item label="API Endpoint" required>
                  <el-input v-model="pform.endpoint" class="mi" placeholder="https://api.openai.com/v1" />
                </el-form-item>
                <el-form-item label="模型名称" required>
                  <el-input v-model="pform.model" class="mi" placeholder="如 deepseek-chat" />
                </el-form-item>
                <el-form-item label="API Key">
                  <el-input
                    v-model="pform.api_key" type="password" show-password class="mi"
                    :placeholder="pform.has_key ? ('已保存 ' + pform.key_masked + '（留空则不变）') : '填入该服务的 API Key'"
                  />
                </el-form-item>
                <el-form-item label="启用">
                  <el-switch v-model="pform.enabled" active-text="参与轮换 / 故障切换" />
                </el-form-item>
                <el-form-item label-width="0">
                  <div class="verify-cell">
                    <el-button :loading="pform.verifying" @click="verifyForm">验证连通</el-button>
                    <span v-if="pform.verify" :class="['verify-result', pform.verify.ok ? 'is-ok' : 'is-bad']">
                      <i class="st-dot" />{{ pform.verify.ok ? '连接正常' : (pform.verify.label || '失败') }}
                    </span>
                  </div>
                </el-form-item>
                <div v-if="pform.verify && !pform.verify.ok && (pform.verify.hint || pform.verify.error)" class="verify-err">
                  {{ pform.verify.label }}：{{ pform.verify.hint || pform.verify.error }}
                </div>
              </el-form>
              <template #footer>
                <el-button @click="providerFormVisible = false">取消</el-button>
                <el-button type="primary" @click="commitProviderForm">保存条目</el-button>
              </template>
            </el-dialog>
          </div>
        </el-tab-pane>

        <!-- ------------------------------ 采集配置 ------------------------------ -->
        <el-tab-pane label="采集配置" name="crawl">
          <div class="tab-body">
            <el-form ref="crawlFormRef" :model="crawlForm" :rules="crawlRules" label-width="112px" class="form-narrow">
              <div class="form-section">
                <div class="section-title">采集来源</div>
                <el-form-item label="来源列表" prop="sources">
                  <el-input v-model="crawlForm.sources" type="textarea" :rows="6" class="mi" placeholder="每行一条，格式：名称|URL" />
                </el-form-item>
              </div>

              <div class="form-section">
                <div class="section-title">采集参数</div>
                <el-row :gutter="12">
                  <el-col :span="12">
                    <el-form-item label="每次抽取上限">
                      <el-input-number v-model="crawlForm.limit" :min="1" :max="50" controls-position="right" class="w-full" />
                    </el-form-item>
                  </el-col>
                  <el-col :span="12">
                    <el-form-item label="上次采集">
                      <el-input v-model="crawlForm.lastAt" readonly class="mi" />
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-form-item label="关键词过滤">
                  <el-checkbox v-model="crawlForm.kwFilter">启用关键词过滤（命中少时自动扩大范围）</el-checkbox>
                </el-form-item>
                <el-form-item label="关键词">
                  <el-input v-model="crawlForm.keywords" placeholder="逗号分隔，如：无人机,林业,病虫害" />
                </el-form-item>
              </div>

              <div class="form-section">
                <div class="section-title">执行</div>
                <el-form-item label-width="0">
                  <el-button type="primary" :loading="crawlSaving" @click="saveCrawl">保存采集配置</el-button>
                  <el-button :icon="Lightning" :loading="crawl.running" @click="doCrawl">立即采集</el-button>
                  <el-button :icon="Document" @click="tab = 'logs'">查看采集日志</el-button>
                </el-form-item>
              </div>
            </el-form>

            <div v-if="crawl.running" class="run-state">
              <span class="run-pulse" />
              <span>采集进行中：<b>{{ crawl.phase }}</b>
                <span class="mono">{{ crawl.progress }}/{{ crawl.total || '–' }}</span>
                {{ crawl.current }}，已生成 <b class="mono">{{ crawl.count }}</b> 条
              </span>
            </div>
            <template v-else-if="crawl.message">
              <div class="run-state run-state--ok">上次：{{ crawl.message }}</div>
              <div v-if="crawl.errors.length" class="run-errors">
                <span class="run-errors-title">本次异常（已按类型识别）</span>
                <span v-for="(e, i) in crawl.errors" :key="i" class="st-pill st-pill--danger err-chip">{{ e }}</span>
              </div>
            </template>
          </div>
        </el-tab-pane>

        <!-- ------------------------------ 采集日志 ------------------------------ -->
        <el-tab-pane :label="logTabLabel" name="logs">
          <div class="tab-body">
            <!-- 概览 -->
            <div class="mini-grid">
              <div class="mini-card">
                <div class="mini-label">采集任务</div>
                <div class="mini-value mono">{{ logStats.total }}</div>
              </div>
              <div class="mini-card">
                <div class="mini-label">新增数据</div>
                <div class="mini-value mono is-ok">{{ logStats.items_total }}</div>
              </div>
              <div class="mini-card">
                <div class="mini-label">异常总数</div>
                <div class="mini-value mono is-bad">{{ logStats.error_total }}</div>
              </div>
              <div class="mini-card">
                <div class="mini-label">成功率</div>
                <div class="mini-value mono">{{ successRate }}</div>
              </div>
            </div>

            <!-- 状态分布 -->
            <div class="chip-bar">
              <span class="bar-label">状态</span>
              <button
                v-for="s in STATUS_LIST"
                :key="s.value"
                type="button"
                :class="['chip', `chip--${s.tag}`, { active: filters.status === s.value }]"
                @click="filters.status = filters.status === s.value ? 'all' : s.value; loadLogs()"
              >{{ s.label }}<span class="chip-n">{{ logStats.by_status[s.value] || 0 }}</span></button>
            </div>

            <!-- 错误类型分布 -->
            <div v-if="logStats.error_types.length" class="chip-bar">
              <span class="bar-label">报错类型</span>
              <el-tooltip v-for="t in logStats.error_types" :key="t.code" :content="typeHint(t.code)" placement="top">
                <button
                  type="button"
                  :class="['chip', `chip--${sevTag(t.severity)}`, { active: filters.error_code === t.code }]"
                  @click="filters.error_code = filters.error_code === t.code ? 'all' : t.code; loadLogs()"
                >{{ t.label }}<span class="chip-n">{{ t.count }}</span></button>
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
                      <div class="sub-head">本次异常明细（{{ row._detail.length }}）</div>
                      <el-table :data="row._detail" size="small" border class="detail-table">
                        <el-table-column label="报错类型" width="140">
                          <template #default="{ row: d }">
                            <span class="st-pill" :class="'st-pill--' + sevTag(d.severity)">{{ d.label }}</span>
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
                <template #default="{ row }"><span class="mono cell-time">{{ fmtTime(row.started_at) }}</span></template>
              </el-table-column>
              <el-table-column prop="task_type" label="任务类型" width="110" show-overflow-tooltip />
              <el-table-column label="状态" width="96" align="center">
                <template #default="{ row }">
                  <span class="st-pill" :class="'st-pill--' + statusTag(row.status)">
                    <i class="st-dot" />{{ statusLabel(row.status) }}
                  </span>
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
                  <span class="mono" :class="{ 'is-ok': row.items_count > 0 }">{{ row.items_count }}</span>
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
                      <span class="st-pill sv-inline" :class="'st-pill--' + sevTag(t.severity)">
                        {{ t.label }} <b class="mono">{{ t.count }}</b>
                      </span>
                    </el-tooltip>
                    <span v-if="row.error_types.length > 2" class="muted">+{{ row.error_types.length - 2 }}</span>
                  </template>
                  <span v-else class="muted">—</span>
                </template>
              </el-table-column>
              <el-table-column label="耗时" width="80" align="right">
                <template #default="{ row }"><span class="mono">{{ fmtDuration(row.duration_ms) }}</span></template>
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
          </div>
        </el-tab-pane>

        <!-- ------------------------------ 技能管理 ------------------------------ -->
        <el-tab-pane :label="`技能管理${skills.length ? ' (' + skills.length + ')' : ''}`" name="skills">
          <div class="tab-body">
            <el-table v-loading="skillsLoading" :data="skills" size="default" empty-text="暂无技能">
              <el-table-column label="技能" min-width="200">
                <template #default="{ row }">
                  <div class="skill-cell">
                    <span class="skill-icon"><el-icon><Tools /></el-icon></span>
                    <span class="skill-name">{{ row.name }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="description" label="说明" min-width="280" show-overflow-tooltip />
              <el-table-column label="状态" width="90" align="center">
                <template #default="{ row }">
                  <span class="st-pill" :class="row.is_builtin || row.is_active ? 'st-pill--success' : 'st-pill--info'">
                    {{ row.is_builtin ? '内置' : row.is_active ? '启用' : '禁用' }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80" align="center">
                <template #default="{ row }">
                  <el-button v-if="!row.is_builtin" link type="danger" size="small" @click="deleteSkill(row.id)">删除</el-button>
                  <span v-else class="muted">—</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- ------------------------------ 新闻采集 ------------------------------ -->
        <el-tab-pane label="新闻采集" name="news">
          <div class="tab-body">
            <el-form label-width="112px" class="form-narrow">
              <div class="form-section">
                <div class="section-title">新闻来源</div>
                <el-form-item label="来源列表">
                  <el-input v-model="newsSources" type="textarea" :rows="4" class="mi" placeholder="每行一条，格式：名称|URL" />
                </el-form-item>
              </div>
              <div class="form-section">
                <div class="section-title">执行</div>
                <el-form-item label-width="0">
                  <el-button type="primary" :loading="newsSaving" @click="saveNews">保存新闻来源</el-button>
                  <el-button :loading="batchLoading" @click="batchCollect">批量采集客户新闻 + 联系人动态</el-button>
                </el-form-item>
              </div>
            </el-form>
            <div class="note-box">
              新闻采集的运行记录已并入「采集日志」标签页，可按任务类型「客户新闻 / 联系人动态」筛选。
              <button type="button" class="link-like" @click="filters.task_type = 'all'; tab = 'logs'">前往采集日志 →</button>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 日志详情抽屉 -->
    <el-drawer v-model="drawer" title="采集日志详情" size="720px" direction="rtl">
      <div v-if="detail" class="drawer-body">
        <DetailGrid :items="drawerItems" dense>
          <template #status>
            <span class="st-pill" :class="'st-pill--' + statusTag(detail.status)">
              <i class="st-dot" />{{ statusLabel(detail.status) }}
            </span>
          </template>
          <template #counts>
            <span class="mono is-ok">{{ detail.items_count }}</span>
            <span class="drawer-sep">/</span>
            <span class="mono is-bad">{{ detail.error_count }}</span>
          </template>
        </DetailGrid>

        <div class="sub-head">报错分类汇总</div>
        <div v-if="detail.error_types && detail.error_types.length" class="chip-bar">
          <span v-for="t in detail.error_types" :key="t.code" class="st-pill" :class="'st-pill--' + sevTag(t.severity)">
            {{ t.label }} <b class="mono">{{ t.count }}</b>
          </span>
        </div>
        <div v-else class="muted">本次采集未产生异常。</div>

        <div class="sub-head">异常明细（{{ (detail.error_detail || []).length }}）</div>
        <el-table :data="detail.error_detail || []" size="small" border empty-text="无">
          <el-table-column label="报错类型" width="130">
            <template #default="{ row }">
              <span class="st-pill" :class="'st-pill--' + sevTag(row.severity)">{{ row.label }}</span>
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
import { Lightning, Tools, Document, Refresh, Search, Delete, Plus } from '@element-plus/icons-vue'
import { get, getList, post, put, del } from '../api'
import { useCrawlStore } from '../stores/app'
import PageHeader from '../components/PageHeader.vue'
import DetailGrid from '../components/DetailGrid.vue'
import PageTable from '../components/PageTable.vue'

const crawl = useCrawlStore()
const tab = ref('ai')

const STATUS_LIST = [
  { value: 'running', label: '进行中', tag: 'info' },
  { value: 'success', label: '成功', tag: 'success' },
  { value: 'partial', label: '部分异常', tag: 'warning' },
  { value: 'failed', label: '失败', tag: 'danger' },
  { value: 'interrupted', label: '已中断', tag: 'info' },
]

const providers = ref([])
const aiSaving = ref(false)
const enabledCount = computed(() => providers.value.filter((p) => p.enabled).length)

// 添加 / 修改 弹窗
const providerFormVisible = ref(false)
const providerEditIndex = ref(null)
const pform = reactive({
  id: '', name: '', endpoint: '', model: '', api_key: '',
  has_key: false, key_masked: '', enabled: true, verifying: false, verify: null,
})
const maskLocal = (k) => '••••' + (k.length >= 4 ? k.slice(-4) : k)

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

// 详情抽屉的字段清单（DetailGrid 新 API：{label, value, full, mono, slot}）
const drawerItems = computed(() => {
  const d = detail.value || {}
  return [
    { label: '任务类型', value: d.task_type },
    { label: '状态', slot: 'status' },
    { label: '开始时间', value: fmtTime(d.started_at), mono: true },
    { label: '结束时间', value: fmtTime(d.finished_at), mono: true },
    { label: '耗时', value: fmtDuration(d.duration_ms), mono: true },
    { label: '新增 / 异常', slot: 'counts' },
    { label: '搜索范围', value: `${d.range_start || '—'} ~ ${d.range_end || '—'}`, full: true, mono: true },
    { label: '关键词', value: d.keywords, full: true },
    { label: '来源', value: d.sources, full: true },
    { label: '结果信息', value: d.message, full: true },
  ]
})

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

async function loadProviders() {
  const list = await getList('/config/ai-providers')
  providers.value = list.map((p) => ({
    id: p.id || '',
    name: p.name || '',
    endpoint: p.endpoint || '',
    model: p.model || '',
    api_key: '',                 // 空 = 不修改，沿用后端已存的 key
    has_key: !!p.has_key,
    key_masked: p.key_masked || '',
    enabled: p.enabled !== false,
    verifying: false,
    verify: null,
  }))
}

function openProviderForm(index = null) {
  providerEditIndex.value = index
  if (index === null) {
    Object.assign(pform, {
      id: '', name: '', endpoint: '', model: '', api_key: '',
      has_key: false, key_masked: '', enabled: true, verifying: false, verify: null,
    })
  } else {
    const p = providers.value[index]
    // 编辑：Key 输入框留空即"不改动"，沿用该行已存的 key
    Object.assign(pform, {
      id: p.id, name: p.name, endpoint: p.endpoint, model: p.model, api_key: '',
      has_key: p.has_key, key_masked: p.key_masked, enabled: p.enabled, verifying: false, verify: null,
    })
  }
  providerFormVisible.value = true
}

async function verifyPayload(obj) {
  return post('/config/verify-ai', {
    id: obj.id, name: obj.name, endpoint: obj.endpoint, model: obj.model, api_key: obj.api_key,
  })
}

async function verifyForm() {
  if (!pform.endpoint || !pform.model) return ElMessage.warning('请先填写 Endpoint 与模型名称')
  pform.verifying = true
  pform.verify = null
  try {
    const r = await verifyPayload(pform)
    if (r.ok) {
      pform.verify = { ok: true }
      ElMessage.success(r.message || '连接正常')
    } else {
      pform.verify = { ok: false, label: r.label, hint: r.hint, error: r.error }
      ElMessage.error(r.label ? `${r.label}：${r.hint || r.error}` : (r.error || '连接失败'))
    }
  } finally {
    pform.verifying = false
  }
}

function commitProviderForm() {
  if (!pform.endpoint || !pform.model) return ElMessage.warning('Endpoint 与模型名称为必填')
  const typed = pform.api_key && !pform.api_key.startsWith('••••') ? pform.api_key : ''
  if (providerEditIndex.value === null && !typed) return ElMessage.warning('请填写 API Key')
  if (providerEditIndex.value === null) {
    providers.value.push({
      id: pform.id, name: pform.name, endpoint: pform.endpoint, model: pform.model,
      api_key: typed, has_key: !!typed, key_masked: typed ? maskLocal(typed) : '',
      enabled: pform.enabled, verifying: false, verify: null,
    })
  } else {
    const p = providers.value[providerEditIndex.value]
    p.name = pform.name
    p.endpoint = pform.endpoint
    p.model = pform.model
    p.enabled = pform.enabled
    if (typed) { p.api_key = typed; p.has_key = true; p.key_masked = maskLocal(typed) }
    // 未填新 key：保留该行原有的 api_key / has_key / key_masked 不变
  }
  providerFormVisible.value = false
}

async function verifyRow(index) {
  const p = providers.value[index]
  if (!p.endpoint || !p.model) return ElMessage.warning('该行 Endpoint 或模型名称缺失')
  p.verifying = true
  try {
    const r = await verifyPayload(p)
    const label = p.name || p.model
    if (r.ok) ElMessage.success(`[${label}] ` + (r.message || '连接正常'))
    else ElMessage.error(r.label ? `[${label}] ${r.label}：${r.hint || r.error}` : (r.error || '连接失败'))
  } finally {
    p.verifying = false
  }
}

function removeProvider(i) {
  const p = providers.value[i]
  const label = p.name || p.model || '该服务'
  ElMessageBox.confirm(`确认删除模型服务「${label}」？点「保存配置」后生效。`, '删除确认', {
    type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
  }).then(() => providers.value.splice(i, 1)).catch(() => {})
}

async function saveProviders() {
  for (const [idx, p] of providers.value.entries()) {
    if (!p.endpoint || !p.model) {
      return ElMessage.warning(`第 ${idx + 1} 家：Endpoint 与模型名称为必填`)
    }
    if (!p.has_key && !p.api_key) {
      return ElMessage.warning(`第 ${idx + 1} 家：请填写 API Key`)
    }
  }
  aiSaving.value = true
  try {
    const body = providers.value.map((p) => ({
      id: p.id, name: p.name, endpoint: p.endpoint, model: p.model,
      api_key: p.api_key, enabled: p.enabled,
    }))
    const r = await put('/config/ai-providers', body)
    if (r.error) return ElMessage.error(r.error)
    ElMessage.success(r.message || 'AI 配置已保存')
    await loadProviders()  // 重新拉取脱敏展示
  } finally {
    aiSaving.value = false
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
  const hasFilter = ['task_type', 'status', 'error_code', 'days'].some((k) => filters[k] && filters[k] !== 'all') || !!filters.q
  if (!hasFilter) return ElMessage.warning('请先设置筛选条件（任务 / 状态 / 报错类型 / 时间 / 关键词），只会清理筛选命中的日志')
  const qs = new URLSearchParams({
    task_type: filters.task_type, status: filters.status,
    error_code: filters.error_code, days: filters.days,
  })
  if (filters.q) qs.set('q', filters.q)
  try {
    await ElMessageBox.confirm(
      '仅清理当前筛选条件命中的采集日志（不影响已采集的线索/客户数据）。是否继续？',
      '清理采集日志', { type: 'warning', confirmButtonText: '清理选中', cancelButtonText: '取消' },
    )
  } catch (e) { return }
  const r = await del('/crawl/logs?' + qs.toString())
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
  loadProviders()
  crawlForm.sources = sourcesToText(config, 'crawl_sources')
  crawlForm.lastAt = config.last_crawl_at?.value || '首次采集（自动回溯最近 7 天）'
  crawlForm.limit = Number(config.crawl_limit?.value || 5) || 5
  crawlForm.kwFilter = (config.crawl_keyword_filter?.value || '1') !== '0'
  crawlForm.keywords = getV('keywords', '无人机,林业,病虫害,巡检')
  newsSources.value = sourcesToText(config, 'news_sources')
  await nextTick()
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
.settings-card {
  background: var(--el-bg-color);
  border: 1px solid var(--crm-border-soft);
  border-radius: var(--crm-radius-lg);
  box-shadow: var(--crm-shadow-xs);
  padding: 2px 22px 22px;
}
.settings-card :deep(.el-tabs__header) { margin-bottom: 16px; }

.tab-body { padding: 2px 0 0; }
.form-section { padding-bottom: 4px; }
.form-narrow { max-width: 640px; }
.w-full { width: 100%; }

/* 代码/URL 输入用等宽字，与全局 .mono 区分：这里穿透到 Element 内部 input */
.mi :deep(.el-input__inner),
.mi :deep(.el-textarea__inner) { font-family: var(--crm-font-mono); font-size: 12.5px; }

.note-box {
  max-width: 700px;
  margin-top: 6px;
  background: var(--crm-slate-25);
  border: 1px solid var(--crm-border-hairline);
  border-radius: var(--crm-radius-md);
  padding: 10px 14px;
  font-size: 12.5px;
  line-height: 1.75;
  color: var(--crm-fg-3);
}
.link-like {
  border: none; background: none; padding: 0 2px; cursor: pointer;
  font-size: 12.5px; color: var(--crm-pine-600); font-weight: 500;
}
.link-like:hover { text-decoration: underline; }

/* 多家 AI 配置（标准列表） */
.ai-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 12px; }
.ai-toolbar .note-box--inline { margin: 0; max-width: 620px; }
.ai-toolbar-actions { display: flex; gap: 8px; flex-shrink: 0; }
.table-wrap { border: 1px solid var(--crm-border-soft); border-radius: var(--crm-radius-lg); overflow: hidden; }
.row-actions { display: inline-flex; align-items: center; gap: 4px; justify-content: flex-end; }
.serial { font-size: 12.5px; color: var(--crm-fg-3); }
.dim { color: var(--crm-fg-3); }
.is-bad { color: var(--crm-rose-500); }
.ai-count { margin-top: 10px; font-size: 12.5px; }
.verify-cell { display: flex; align-items: center; gap: 10px; min-height: 24px; }
.verify-result { display: inline-flex; align-items: center; gap: 5px; font-size: 12.5px; }
.verify-result.is-ok { color: var(--crm-pine-600); }
.verify-result.is-bad { color: var(--crm-rose-500); }
.verify-err {
  margin: 0 0 4px 104px; font-size: 12.5px; line-height: 1.6;
  color: var(--crm-rose-500);
  background: var(--crm-rose-50);
  border: 1px solid var(--crm-border-hairline);
  border-radius: var(--crm-radius-sm);
  padding: 6px 10px;
}

/* 采集运行状态 */
.run-state {
  display: flex; align-items: center; flex-wrap: wrap; gap: 8px;
  max-width: 700px; margin-top: 4px;
  background: var(--crm-sky-50);
  border: 1px solid var(--crm-border-hairline);
  border-radius: var(--crm-radius-md);
  padding: 10px 14px; font-size: 13px; color: var(--crm-fg-2); line-height: 1.7;
}
.run-state--ok { background: var(--crm-pine-25); }
.run-pulse {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--crm-sky-500); position: relative; flex-shrink: 0;
}
.run-pulse::after {
  content: ''; position: absolute; inset: -4px; border-radius: 50%;
  border: 1px solid var(--crm-sky-500); opacity: .5;
  animation: run-ping 1.4s var(--crm-ease-out) infinite;
}
@keyframes run-ping {
  0% { transform: scale(.6); opacity: .6; }
  100% { transform: scale(1.5); opacity: 0; }
}
.run-errors { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.run-errors-title { font-size: 12.5px; color: var(--crm-fg-3); margin-right: 4px; }
.err-chip { max-width: 100%; }

/* 概览小卡 */
.mini-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
.mini-card {
  background: var(--crm-slate-25);
  border: 1px solid var(--crm-border-hairline);
  border-radius: var(--crm-radius-md);
  padding: 11px 14px;
}
.mini-label { font-size: 12px; color: var(--crm-fg-3); }
.mini-value { font-size: 21px; font-weight: 650; margin-top: 3px; color: var(--crm-fg-1); letter-spacing: -0.02em; }
.mini-value.is-ok { color: var(--crm-pine-600); }
.mini-value.is-bad { color: var(--crm-rose-500); }

/* 可点击过滤 chip */
.chip-bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px; }
.bar-label { font-size: 12.5px; color: var(--crm-fg-3); margin-right: 2px; }
.chip {
  display: inline-flex; align-items: center; gap: 6px;
  height: 25px; padding: 0 10px; border-radius: var(--crm-radius-full);
  border: 1px solid var(--crm-border-hairline);
  background: transparent; color: var(--crm-fg-2);
  font-size: 12px; line-height: 1; cursor: pointer;
  transition: border-color var(--crm-dur-fast) var(--crm-ease-out),
              background var(--crm-dur-fast) var(--crm-ease-out),
              color var(--crm-dur-fast) var(--crm-ease-out);
}
.chip:hover { border-color: var(--crm-pine-300); color: var(--crm-fg-1); }
.chip-n { font-family: var(--crm-font-mono); font-size: 11px; color: var(--crm-fg-4); font-style: normal; }
.chip.active { border-color: currentColor; font-weight: 500; }
.chip.active .chip-n { color: inherit; }
.chip--info.active { color: var(--crm-fg-2); background: var(--crm-slate-100); }
.chip--success.active { color: var(--crm-pine-600); background: var(--crm-pine-25); }
.chip--warning.active { color: var(--crm-amber-500); background: var(--crm-amber-50); }
.chip--danger.active { color: var(--crm-rose-500); background: var(--crm-rose-50); }

/* 日志筛选行 */
.log-filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 6px 0 12px; }
.f-select { width: 128px; }
.f-select.wide { width: 168px; }
.f-search { width: 220px; }
.grow { flex: 1; }

/* 状态 / 报错语义胶囊 */
.st-pill {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 1px 8px; border-radius: var(--crm-radius-full);
  font-size: 12px; line-height: 18px; white-space: nowrap;
}
.st-pill--info { color: var(--crm-fg-2); background: var(--crm-slate-100); }
.st-pill--success { color: var(--crm-pine-600); background: var(--crm-pine-25); }
.st-pill--warning { color: var(--crm-amber-500); background: var(--crm-amber-50); }
.st-pill--danger { color: var(--crm-rose-500); background: var(--crm-rose-50); }
.st-dot { width: 5px; height: 5px; border-radius: 50%; background: currentColor; flex-shrink: 0; }
.sv-inline { margin-right: 4px; }

.cell-time { font-size: 12.5px; }
.is-ok { color: var(--crm-pine-600); }
.is-bad { color: var(--crm-rose-500); }

/* 展开明细 / 抽屉 */
.detail-wrap { padding: 8px 12px 12px; }
.sub-head { font-size: 13px; font-weight: 650; color: var(--crm-fg-1); margin: 18px 0 8px; }
.detail-table { margin-bottom: 4px; }
.pager { margin-top: 12px; justify-content: flex-end; }
.drawer-body { padding-bottom: 20px; }
.drawer-sep { margin: 0 6px; color: var(--crm-fg-4); }

/* 技能单元格 */
.skill-cell { display: flex; align-items: center; gap: 9px; }
.skill-icon {
  width: 26px; height: 26px; border-radius: var(--crm-radius-sm);
  background: var(--crm-pine-25); color: var(--crm-pine-600);
  display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.skill-name { font-weight: 550; color: var(--crm-fg-1); }

.muted { color: var(--crm-fg-3); font-size: 12.5px; }

@media (max-width: 720px) {
  .mini-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .settings-card { padding: 2px 14px 16px; }
}
</style>
