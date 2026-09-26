<template>
  <div class="page">
    <!-- 顶部：标题 + 视图切换 + 主操作 -->
    <PageHeader title="商机管理" subtitle="阶段推进、赢率评估与联络沉淀">
      <template #actions>
        <div class="seg-group seg-group--sm" role="tablist">
          <button class="seg-btn" :class="{ 'is-active': view === 'list' }" @click="view = 'list'">
            <el-icon :size="13"><List /></el-icon>列表
          </button>
          <button class="seg-btn" :class="{ 'is-active': view === 'board' }" @click="view = 'board'">
            <el-icon :size="13"><Grid /></el-icon>看板
          </button>
        </div>
        <el-button :icon="Download" plain @click="doExport">导出</el-button>
        <el-button type="primary" :icon="Plus" @click="openForm()">新建商机</el-button>
      </template>
    </PageHeader>

    <!-- 阶段管道：点击阶段可过滤 -->
    <div class="stage-rail">
      <button
        v-for="s in stageData" :key="s.name"
        class="stage-node" :class="{ 'is-active': filter.stage === s.name }"
        @click="toggleStage(s.name)"
      >
        <div class="stage-head">
          <span class="stage-dot" :style="{ background: s.color }"></span>
          <span class="stage-name">{{ s.name }}</span>
          <span class="stage-count mono">{{ s.items.length }}</span>
        </div>
        <div class="stage-amount mono muted">{{ sumAmount(s.items) }}<i>万</i></div>
        <div class="stage-bar"><i :style="{ width: stagePct(s), background: s.color }"></i></div>
      </button>
    </div>

    <!-- 搜索 -->
    <FilterBar @search="applyFilter" @reset="resetFilter">
      <el-form-item label="名称">
        <el-input v-model="draft.q" placeholder="商机名称 / 客户" clearable style="width:220px" />
      </el-form-item>
      <el-form-item label="客户">
        <el-select v-model="draft.customer" clearable filterable style="width:190px" placeholder="全部客户" @change="applyFilter">
          <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
        </el-select>
      </el-form-item>
      <el-form-item label="阶段">
        <el-select v-model="draft.stage" clearable style="width:150px" placeholder="全部阶段" @change="applyFilter">
          <el-option v-for="s in dict.stageNames" :key="s" :value="s" :label="s" />
        </el-select>
      </el-form-item>
      <el-form-item label="创建从">
        <el-date-picker v-model="draft.from" type="date" value-format="YYYY-MM-DD" placeholder="起始" style="width:150px" @change="applyFilter" />
      </el-form-item>
      <el-form-item label="创建至">
        <el-date-picker v-model="draft.to" type="date" value-format="YYYY-MM-DD" placeholder="结束" style="width:150px" @change="applyFilter" />
      </el-form-item>
    </FilterBar>

    <!-- 列表视图 -->
    <div v-if="view === 'list'" class="table-wrap">
      <PageTable
        storage-key="opp"
        :data="filteredList"
        :loading="loading"
        :default-sort="{ prop: 'created_at', order: 'descending' }"
        empty-text="暂无商机"
        empty-hint="转化线索或直接新建，开始跟踪你的销售 pipeline"
      >
        <template #empty-action>
          <el-button type="primary" plain size="small" :icon="Plus" @click="openForm()" style="margin-top:12px">新建商机</el-button>
        </template>

        <el-table-column prop="id" label="编号" width="86" sortable="custom">
          <template #default="{ row }">
            <span class="mono serial">{{ oppNo(row.id) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="商机名称" min-width="240" sortable="custom">
          <template #default="{ row }">
            <div class="cell-title-text is-link" :title="row.title" @click="viewDetail(row.id)">{{ row.title }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="customer_name" label="客户" min-width="150" sortable="custom" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.customer_name">{{ row.customer_name }}</span>
            <span v-else class="dim">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="amount" label="金额(万)" width="106" sortable="custom" align="right">
          <template #default="{ row }">
            <span v-if="row.amount" class="mono amount">{{ fmtBudgetNum(row.amount) }}</span>
            <span v-else class="mono dim">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="current_stage" label="阶段" width="118" sortable="custom">
          <template #default="{ row }">
            <span class="stage-pill">
              <i class="stage-pill-dot" :style="{ background: stageColorOf(row.current_stage) }"></i>
              {{ row.current_stage || '—' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="probability" label="赢率" width="104" sortable="custom">
          <template #default="{ row }">
            <div class="prob-cell">
              <span class="mono prob-num" :style="{ color: probColor(row.probability || 20) }">{{ row.probability || 20 }}%</span>
              <span class="prob-bar"><i :style="{ width: (row.probability || 20) + '%', background: probColor(row.probability || 20) }"></i></span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="contact_name" label="联系人" width="100">
          <template #default="{ row }">
            <span v-if="row.contact_name">{{ row.contact_name }}</span>
            <span v-else class="dim">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="expected_close" label="预计关闭" width="112" sortable="custom">
          <template #default="{ row }">
            <span v-if="row.expected_close" class="mono date" :class="{ 'is-urgent': isCloseSoon(row) }">
              {{ fmtDateMDY(row.expected_close) }}
            </span>
            <span v-else class="mono dim">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right" align="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button link size="small" @click.stop="openForm(row.id)">编辑</el-button>
              <el-button link type="danger" size="small" @click.stop="deleteOpp(row.id)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </PageTable>
    </div>

    <!-- 看板视图：卡片可拖拽换阶段（用户反馈 8） -->
    <div v-else class="opp-board">
      <div
        v-for="s in stageData" :key="s.name"
        class="board-col" :class="{ 'is-over': dropStage === s.name }"
        @dragover="onDragOver(s.name, $event)" @dragleave="onDragLeave(s.name)" @drop="onDropStage(s.name)"
      >
        <div class="board-col-head">
          <span class="stage-dot" :style="{ background: s.color }"></span>
          <span class="board-col-name">{{ s.name }}</span>
          <span class="board-col-count mono">{{ s.items.length }}</span>
        </div>
        <div class="board-col-sum mono muted">{{ sumAmount(s.items) }} 万</div>
        <div class="board-col-cards">
          <div
            v-for="o in s.items" :key="o.id"
            class="board-card" :class="{ 'is-dragging': dragId === o.id }"
            draggable="true"
            @dragstart="onDragStart(o, $event)" @dragend="onDragEnd"
            @click="viewDetail(o.id)"
          >
            <div class="board-card-top">
              <span class="mono board-card-no">{{ oppNo(o.id) }}</span>
              <el-icon class="board-card-grip" :size="14"><Rank /></el-icon>
            </div>
            <div class="board-card-title">{{ o.title }}</div>
            <div class="board-card-cust muted">{{ o.customer_name || '未关联客户' }}</div>
            <div class="board-card-foot">
              <span class="mono board-card-amount">{{ fmtBudgetNum(o.amount) }}万</span>
              <span class="mono" :style="{ color: probColor(o.probability || 20) }">{{ o.probability || 20 }}%</span>
            </div>
          </div>
          <div v-if="!s.items.length" class="board-col-empty">
            <span class="muted">{{ dragId ? '拖到这里' : '空' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 新建 / 编辑商机 -->
    <el-dialog v-model="formVisible" :title="editId ? '编辑商机' : '新建商机'" width="720px" destroy-on-close class="form-dialog">
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="98px" label-position="right">
        <div class="form-section">
          <div class="section-title">基本信息</div>
          <el-form-item label="商机名称" prop="title">
            <el-input v-model="form.title" placeholder="如：四川省林草无人机监测服务平台" maxlength="200" show-word-limit />
          </el-form-item>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="阶段" prop="current_stage">
                <el-select v-model="form.current_stage" style="width:100%">
                  <el-option v-for="s in dict.stageNames" :key="s" :value="s" :label="s" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="预计关闭">
                <el-date-picker v-model="form.expected_close" type="date" value-format="YYYY-MM-DD" style="width:100%" />
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <div class="form-section">
          <div class="section-title">客户与联系人</div>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="客户">
                <el-select v-model="form.customer_id" clearable filterable style="width:100%" placeholder="从客户库选择">
                  <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="联系人">
                <el-select v-model="form.contact_id" clearable filterable style="width:100%" placeholder="从联系人库选择">
                  <el-option v-for="c in dict.contacts" :key="c.id" :value="c.id" :label="c.name" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <div class="form-section">
          <div class="section-title">评估</div>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="金额(万)">
                <el-input-number v-model="form.amount" :min="0" :precision="2" controls-position="right" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="赢率(%)">
                <el-input-number v-model="form.probability" :min="0" :max="100" :step="5" controls-position="right" style="width:100%" />
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <div class="form-section">
          <div class="section-title">来源</div>
          <el-form-item label="原文链接">
            <el-input v-model="form.source_url" placeholder="https://（选填，线索转化的商机自动带上）" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingForm" @click="saveForm">{{ editId ? '保存修改' : '创建商机' }}</el-button>
      </template>
    </el-dialog>

    <!-- 商机详情 -->
    <el-dialog v-model="detailVisible" title="商机详情" width="780px" destroy-on-close class="detail-dialog">
      <div v-loading="detailLoading" class="detail-loading-wrap">
        <template v-if="detail">
          <div class="detail-hero">
            <div class="detail-hero-body">
              <div class="detail-hero-title">{{ detail.title }}</div>
              <div class="detail-hero-meta">
                <span class="mono hero-serial">{{ oppNo(detail.id) }}</span>
                <span class="stage-pill">
                  <i class="stage-pill-dot" :style="{ background: stageColorOf(detail.current_stage) }"></i>
                  {{ detail.current_stage || '—' }}
                </span>
                <span v-if="detail.customer_name" class="hero-chip">{{ detail.customer_name }}</span>
                <span v-if="detail.amount" class="mono hero-amount">{{ fmtBudgetNum(detail.amount) }} 万</span>
                <span v-if="detail.created_at" class="muted">创建于 {{ detail.created_at }}</span>
              </div>
            </div>
          </div>

          <div class="detail-body">
            <div class="section-title">项目信息</div>
            <DetailGrid :items="[
              { label: '客户', value: detail.customer_name },
              { label: '联系人', value: detail.contact_name },
              { label: '金额', value: detail.amount ? fmtBudgetNum(detail.amount) + ' 万' : '', mono: true },
              { label: '预计关闭', value: fmtDate(detail.expected_close) || '', mono: true },
              { label: '来源', slot: 'src' },
            ]">
              <template #src>
                <el-link v-if="detail.source_url" type="primary" :href="detail.source_url" target="_blank" :underline="false" class="source-link">查看招标原文</el-link>
                <span v-else class="muted">手工添加</span>
              </template>
            </DetailGrid>

            <div class="section-title">流转时间轴<i class="sec-count">{{ acts.length }}</i></div>
            <div v-if="acts.length" class="act-list">
              <div v-for="a in acts" :key="a.id" class="act-item">
                <span class="act-rail-dot" :class="{ 'is-first': a === acts[0] }"></span>
                <div class="act-body">
                  <div class="act-head">
                    <span class="act-time mono">{{ fmtDate(a.activity_time) || '—' }}</span>
                    <span v-if="a.method" class="act-method">{{ a.method }}</span>
                    <span v-if="a.contact_name" class="muted act-contact">联系人: {{ a.contact_name }}</span>
                  </div>
                  <div class="act-content">{{ a.content }}</div>
                  <div v-if="a.next_followup_time" class="act-next">
                    预计下次跟进 {{ fmtDate(a.next_followup_time) }}<span v-if="a.next_followup_content"> · {{ a.next_followup_content }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="list-empty muted">暂无联络记录，可在「日常联络」中补充</div>

            <template v-if="(detail.stages || []).length">
              <div class="section-title">阶段记录<i class="sec-count">{{ detail.stages.length }}</i></div>
              <div class="stage-rec-list">
                <div v-for="(s, i) in detail.stages" :key="i" class="stage-rec">
                  <span class="stage-pill">
                    <i class="stage-pill-dot" :style="{ background: stageColorOf(s.stage) }"></i>
                    {{ s.stage }}
                  </span>
                  <span class="stage-rec-content" v-if="s.content">{{ s.content }}</span>
                  <span class="stage-rec-time mono muted">{{ fmtDate(s.created_at) }}</span>
                </div>
              </div>
            </template>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button v-if="detail" :icon="Edit" @click="openForm(detail.id)">编辑商机</el-button>
        <el-button v-if="detail" type="primary" :icon="Plus" @click="addActivity">添加联络记录</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Download, Edit, List, Grid, Rank } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'
import PageTable from '../components/PageTable.vue'
import FilterBar from '../components/FilterBar.vue'
import DetailGrid from '../components/DetailGrid.vue'
import { get, getList, post, put, del, fmtDate, fmtDateMDY, fmtNum, exportCsv, probColor, stageColor } from '../api'
import { useDictStore } from '../stores/app'

const route = useRoute()
const router = useRouter()
const dict = useDictStore()
const opps = ref([])
const loading = ref(false)
const view = ref('list')
const filter = reactive({ q: '', customer: '', stage: '', from: '', to: '' })
const draft = reactive({ q: '', customer: '', stage: '', from: '', to: '' })

// 编号：与线索一致的 6 位补零展示（id 即库内自增主键，稳定可检索）
const oppNo = (id) => (id === null || id === undefined ? '—' : String(id).padStart(6, '0'))
// 部分历史数据把单位写进了金额（"2万"），列表/详情列头已带(万)，展示前去尾缀
const fmtBudgetNum = (v) => fmtNum(String(v).replace(/[^\d.\-]/g, ''))

const filteredList = computed(() => opps.value.filter((o) => {
  if (filter.q && !((o.title || '').toLowerCase().includes(filter.q.toLowerCase())
    || (o.customer_name || '').includes(filter.q))) return false
  if (filter.customer && String(o.customer_id) !== String(filter.customer)) return false
  if (filter.stage && o.current_stage !== filter.stage) return false
  const cd = fmtDate(o.created_at)
  if (filter.from && cd && cd < filter.from) return false
  if (filter.to && cd && cd > filter.to) return false
  return true
}))

const stageData = computed(() => dict.stageNames.map((s) => ({
  name: s,
  color: stageColor(s, dict.stageNames),
  items: filteredList.value.filter((o) => o.current_stage === s),
})))
const stageColorOf = (name) => {
  const s = stageData.value.find((x) => x.name === name)
  return s ? s.color : 'var(--crm-slate-400)'
}
const stagePct = (s) => {
  const total = filteredList.value.length || 1
  return Math.round((s.items.length / total) * 100) + '%'
}
const toggleStage = (name) => {
  draft.stage = filter.stage === name ? '' : name
  applyFilter()
}

const sumAmount = (items) => fmtNum(items.reduce((a, o) => a + parseFloat(o.amount || 0), 0))

const isCloseSoon = (row) => {
  if (!row.expected_close) return false
  const t = new Date(row.expected_close + 'T23:59:59').getTime()
  return t - Date.now() <= 14 * 86400000
}

async function load() {
  loading.value = true
  opps.value = await getList('/opportunities')
  loading.value = false
}
function applyFilter() { Object.assign(filter, draft) }
function resetFilter() {
  Object.assign(draft, { q: '', customer: '', stage: '', from: '', to: '' })
  Object.assign(filter, draft)
}

// ---- 看板拖拽换阶段（用户反馈 8）----
const dragId = ref(null)
const dropStage = ref('')
function onDragStart(o, ev) {
  dragId.value = o.id
  if (ev.dataTransfer) {
    ev.dataTransfer.effectAllowed = 'move'
    try { ev.dataTransfer.setData('text/plain', String(o.id)) } catch (e) { /* Safari 隐私限制 */ }
  }
}
function onDragEnd() { dragId.value = null; dropStage.value = '' }
function onDragOver(stage, ev) {
  if (dragId.value == null) return
  ev.preventDefault()
  if (ev.dataTransfer) ev.dataTransfer.dropEffect = 'move'
  dropStage.value = stage
}
function onDragLeave(stage) { if (dropStage.value === stage) dropStage.value = '' }
async function onDropStage(stage) {
  dropStage.value = ''
  const id = dragId.value
  dragId.value = null
  if (id == null) return
  const o = opps.value.find((x) => x.id === id)
  if (!o || o.current_stage === stage) return
  const prev = o.current_stage
  o.current_stage = stage // 乐观更新：拖完立即换位，失败再回滚
  const r = await put(`/opportunities/${id}`, { current_stage: stage })
  if (r.error) {
    o.current_stage = prev
    return ElMessage.error('调整阶段失败：' + r.error)
  }
  ElMessage.success(`已移至「${stage}」`)
  dict.loadOpportunities()
}

// ---- 新建 / 编辑 ----
const formVisible = ref(false)
const editId = ref(null)
const formRef = ref(null)
const savingForm = ref(false)
const form = reactive({})
const formRules = {
  title: [{ required: true, message: '请输入商机名称', trigger: 'blur' }],
  current_stage: [{ required: true, message: '请选择阶段', trigger: 'change' }],
}

function openForm(id) {
  editId.value = id || null
  Object.keys(form).forEach((k) => delete form[k])
  Object.assign(form, {
    title: '', customer_id: null, contact_id: null, amount: null, probability: 20,
    current_stage: dict.stageNames[0] || '', expected_close: '', source_url: '',
  })
  if (id) {
    get(`/opportunities/${id}`).then((o) => {
      Object.keys(form).forEach((k) => { form[k] = o[k] ?? form[k] })
      form.amount = o.amount === null || o.amount === undefined || o.amount === '' ? null : Number(o.amount)
      form.probability = Number(o.probability ?? 20)
    })
  }
  formVisible.value = true
  nextTick(() => formRef.value?.clearValidate())
}

async function saveForm() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  savingForm.value = true
  try {
    const d = { ...form, probability: parseInt(form.probability) || 20 }
    const r = editId.value ? await put(`/opportunities/${editId.value}`, d) : await post('/opportunities', d)
    if (r.error) return ElMessage.error(r.error)
    ElMessage.success(editId.value ? '更新成功' : '创建成功')
    formVisible.value = false
    load(); dict.loadOpportunities()
  } finally {
    savingForm.value = false
  }
}

async function deleteOpp(id) {
  try {
    await ElMessageBox.confirm('确认删除该商机？', '删除商机', { type: 'warning' })
  } catch (e) { return }
  const r = await del(`/opportunities/${id}`)
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success('已删除'); load()
}

// ---- 详情 ----
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref(null)
const acts = computed(() => (detail.value?.activities || []).slice().reverse())

async function viewDetail(id) {
  // 先取数再开窗：get() 失败返回 truthy 的 { error }，
  // 直接赋给 detail 会弹出一个"有壳没肉"的空白详情（用户反馈 9）
  detailLoading.value = true
  try {
    const r = await get(`/opportunities/${id}`)
    if (r.error) return ElMessage.error('加载商机详情失败：' + r.error)
    detail.value = r
    detailVisible.value = true
  } finally {
    detailLoading.value = false
  }
}

// 跳转到日常联络并预填商机，改用路由 query（原先用 window._presetActivity + 直接改 hash，刷新即丢）
function addActivity() {
  detailVisible.value = false
  router.push({
    path: '/contactlog',
    query: { opportunityId: detail.value.id, customerId: detail.value.customer_id },
  })
}

async function doExport() {
  const err = await exportCsv('opportunities', filteredList.value)
  err ? ElMessage.error(err) : ElMessage.success(`已导出 ${filteredList.value.length} 条`)
}

onMounted(async () => {
  await Promise.all([load(), dict.loadCustomers(), dict.loadContacts(), dict.loadStages()])
  // 从客户详情跳来时通过 query 打开指定商机（原先靠 window._presetOppDetail 全局变量）
  if (route.query.oppId) viewDetail(Number(route.query.oppId))
})
</script>

<style scoped>
/* ---- 视图切换（小号分段，放 PageHeader actions 里） ---- */
.seg-group {
  display: inline-flex; padding: 3px; gap: 2px;
  background: var(--crm-slate-100);
  border-radius: 9px;
  border: 1px solid var(--crm-border-soft);
}
.seg-btn {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 0 12px; height: 28px;
  border: none; background: transparent; cursor: pointer;
  font-family: inherit; font-size: 12.5px; font-weight: 500;
  color: var(--crm-fg-3);
  border-radius: 6px;
  transition: all var(--crm-dur-fast) var(--crm-ease-out);
}
.seg-btn:hover { color: var(--crm-fg-1); }
.seg-btn.is-active {
  background: var(--crm-bg-card); color: var(--crm-fg-1);
  box-shadow: var(--crm-shadow-xs);
  font-weight: 600;
}

/* ---- 阶段管道条 ---- */
.stage-rail {
  display: flex; gap: 10px; margin-bottom: 14px;
  overflow-x: auto; padding-bottom: 2px;
}
.stage-node {
  flex: 1 1 0; min-width: 128px;
  display: flex; flex-direction: column; gap: 4px; align-items: flex-start;
  padding: 12px 14px 14px;
  background: var(--crm-bg-card);
  border: 1px solid var(--crm-border-soft);
  border-radius: var(--crm-radius-lg);
  cursor: pointer; text-align: left;
  font-family: inherit;
  transition: border-color var(--crm-dur-fast) var(--crm-ease-out),
    box-shadow var(--crm-dur-fast) var(--crm-ease-out),
    background var(--crm-dur-fast) var(--crm-ease-out);
}
.stage-node:hover { box-shadow: var(--crm-shadow-sm); border-color: var(--crm-border-hairline); }
.stage-node.is-active {
  border-color: var(--crm-pine-300);
  background: var(--crm-pine-25);
  box-shadow: var(--crm-shadow-xs);
}
.stage-head { display: flex; align-items: center; gap: 6px; width: 100%; }
.stage-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.stage-name {
  font-size: 12.5px; font-weight: 500; color: var(--crm-fg-2);
  flex: 1; min-width: 0;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.stage-count { font-size: 15px; font-weight: 700; color: var(--crm-fg-1); letter-spacing: -0.02em; }
.stage-amount { font-size: 12px; }
.stage-amount i { font-style: normal; font-size: 11px; margin-left: 1px; }
.stage-bar {
  width: 100%; height: 3px; border-radius: 2px;
  background: var(--crm-slate-100); overflow: hidden; margin-top: 2px;
}
.stage-bar i { display: block; height: 100%; border-radius: 2px; transition: width var(--crm-dur-slow) var(--crm-ease-out); }

/* ---- 表格容器 ---- */
.table-wrap {
  background: var(--crm-bg-card);
  border: 1px solid var(--crm-border-soft);
  border-radius: var(--crm-radius-lg);
  overflow: hidden;
  box-shadow: var(--crm-shadow-xs);
}

/* ---- 单元格 ---- */
.serial { font-size: 12px; color: var(--crm-fg-3); letter-spacing: -0.02em; }
.cell-title-text {
  color: var(--crm-fg-1); font-weight: 500; font-size: 13.5px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  line-height: 1.45;
}
.cell-title-text.is-link {
  cursor: pointer; text-decoration: underline;
  text-underline-offset: 2px; text-decoration-thickness: 1px;
  text-decoration-color: var(--crm-border-strong);
}
.cell-title-text.is-link:hover { color: var(--crm-pine-600); text-decoration-color: var(--crm-pine-600); }
.cell-meta { font-size: 11.5px; color: var(--crm-fg-3); margin-top: 3px; }
.src-tag { color: var(--crm-pine-600); font-weight: 500; }
.hero-serial {
  font-size: 11.5px; padding: 1px 6px; border-radius: var(--crm-radius-sm);
  background: var(--crm-slate-100); color: var(--crm-fg-3); letter-spacing: -0.02em;
}
.amount { color: var(--crm-fg-1); font-weight: 600; font-size: 13px; }
.date { font-size: 12px; }
.date.is-urgent { color: var(--crm-rose-500); font-weight: 600; }
.row-actions { display: inline-flex; gap: 0; justify-content: flex-end; align-items: center; }
.row-actions :deep(.el-button.is-link) { padding: 2px 6px; }

.stage-pill {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 2px 8px 2px 6px;
  font-size: 11.5px; font-weight: 500; color: var(--crm-fg-2);
  border-radius: var(--crm-radius-full);
  background: var(--crm-slate-100);
  white-space: nowrap; max-width: 100%;
}
.stage-pill-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }

.prob-cell { display: flex; flex-direction: column; gap: 4px; }
.prob-num { font-size: 12.5px; font-weight: 600; }
.prob-bar { display: block; height: 3px; border-radius: 2px; background: var(--crm-slate-100); overflow: hidden; }
.prob-bar i { display: block; height: 100%; border-radius: 2px; }

/* ---- 看板视图 ---- */
.opp-board { display: flex; gap: 12px; overflow-x: auto; padding-bottom: 8px; align-items: flex-start; }
.board-col {
  flex: 1 1 0; min-width: 236px; max-width: 320px;
  background: var(--crm-slate-25);
  border: 1px solid var(--crm-border-soft);
  border-radius: var(--crm-radius-lg);
  padding: 12px 10px 10px;
  transition: border-color var(--crm-dur-fast) var(--crm-ease-out),
    background var(--crm-dur-fast) var(--crm-ease-out);
}
.board-col.is-over {
  border-color: var(--crm-pine-300);
  background: var(--crm-pine-25);
}
.board-col-head { display: flex; align-items: center; gap: 7px; padding: 0 4px 2px; }
.board-col-name { font-size: 13px; font-weight: 600; color: var(--crm-fg-1); flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.board-col-count {
  font-size: 11px; padding: 1px 7px; border-radius: 8px;
  background: var(--crm-slate-100); color: var(--crm-fg-3); min-width: 20px; text-align: center;
}
.board-col-sum { padding: 0 4px 10px; font-size: 11.5px; }
.board-col-cards { display: flex; flex-direction: column; gap: 8px; max-height: calc(100vh - 320px); overflow-y: auto; }
.board-card {
  background: var(--crm-bg-card);
  border: 1px solid var(--crm-border-soft);
  border-radius: var(--crm-radius-md);
  padding: 11px 12px; cursor: grab;
  box-shadow: var(--crm-shadow-xs);
  transition: border-color var(--crm-dur-fast) var(--crm-ease-out),
    box-shadow var(--crm-dur-fast) var(--crm-ease-out),
    transform var(--crm-dur-fast) var(--crm-ease-out),
    opacity var(--crm-dur-fast) var(--crm-ease-out);
}
.board-card:active { cursor: grabbing; }
.board-card.is-dragging { opacity: 0.45; transform: scale(0.98); border-style: dashed; }
.board-card-top {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 4px; min-height: 16px;
}
.board-card-no { font-size: 10.5px; color: var(--crm-fg-4); letter-spacing: -0.02em; }
.board-card-grip { color: var(--crm-slate-400); opacity: 0.55; }
.board-card:hover { border-color: var(--crm-pine-300); box-shadow: var(--crm-shadow-sm); transform: translateY(-1px); }
.board-card:hover .board-card-grip { opacity: 1; }
.board-card-title {
  font-weight: 500; font-size: 13px; color: var(--crm-fg-1); line-height: 1.45;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.board-card-cust { font-size: 11.5px; margin: 4px 0 8px; }
.board-card-foot { display: flex; justify-content: space-between; font-size: 12px; }
.board-card-amount { font-weight: 600; color: var(--crm-fg-1); }
.board-col-empty { padding: 18px 0; text-align: center; font-size: 12px; }

/* ---- 表单分组 ---- */
.form-section { margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px dashed var(--crm-border-soft); }
.form-section:last-child { margin-bottom: 0; padding-bottom: 0; border-bottom: none; }

/* ---- 详情弹窗 ---- */
.detail-dialog :deep(.el-dialog__body) { padding: 0 !important; }
.detail-loading-wrap { min-height: 120px; }
.detail-hero {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 14px 20px 12px;
  background: linear-gradient(180deg, var(--crm-pine-25) 0%, var(--crm-bg-card) 100%);
  border-bottom: 1px solid var(--crm-border-soft);
}
.detail-hero-body { flex: 1; min-width: 0; }
.detail-hero-title {
  font-family: var(--crm-font-display);
  font-size: 16px; font-weight: 600; color: var(--crm-fg-1);
  line-height: 1.4; letter-spacing: -0.011em;
  margin-bottom: 6px;
  word-break: break-word; overflow-wrap: anywhere;
}
.detail-hero-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 12px; color: var(--crm-fg-3); }
.hero-chip {
  padding: 1px 8px; border-radius: var(--crm-radius-sm);
  background: var(--crm-slate-100); color: var(--crm-fg-2); font-size: 12px;
}
.hero-amount { font-size: 13px; font-weight: 600; color: var(--crm-fg-1); }
.detail-hero-side { flex-shrink: 0; display: flex; flex-direction: column; align-items: center; gap: 4px; }
.prob-ring {
  --size: 64px;
  width: var(--size); height: var(--size);
  border-radius: 50%;
  display: flex; align-items: baseline; justify-content: center; padding-top: 18px;
  background: conic-gradient(var(--ring) calc(var(--ring-percent) * 1%), var(--crm-slate-100) 0);
  position: relative;
}
.prob-ring::before { content: ''; position: absolute; inset: 6px; border-radius: 50%; background: var(--crm-bg-card); }
.prob-ring-num { position: relative; font-family: var(--crm-font-display); font-size: 20px; font-weight: 700; color: var(--crm-fg-1); letter-spacing: -0.02em; }
.prob-ring-unit { position: relative; font-size: 11px; color: var(--crm-fg-3); margin-left: 1px; }
.prob-ring-label { font-size: 11.5px; color: var(--crm-fg-3); font-weight: 500; }

.detail-body { padding: 14px 20px 8px; }

/* 联络时间轴（自定义，替代 el-timeline） */
.act-list { display: flex; flex-direction: column; }
.act-item { display: flex; gap: 12px; position: relative; padding-bottom: 14px; }
.act-item::before {
  content: ''; position: absolute; left: 4px; top: 14px; bottom: 0;
  width: 1px; background: var(--crm-border-soft);
}
.act-item:last-child::before { display: none; }
.act-rail-dot {
  width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; margin-top: 5px;
  background: var(--crm-slate-300); border: 2px solid var(--crm-bg-card);
  box-shadow: 0 0 0 1px var(--crm-border-hairline);
  position: relative; z-index: 1;
}
.act-rail-dot.is-first { background: var(--crm-pine-500); box-shadow: 0 0 0 1px var(--crm-pine-500); }
.act-body { flex: 1; min-width: 0; }
.act-head { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.act-time { font-size: 11.5px; color: var(--crm-fg-3); }
.act-method {
  font-size: 11px; padding: 0 6px; border-radius: var(--crm-radius-sm);
  background: var(--crm-pine-25); color: var(--crm-pine-600); font-weight: 500;
}
.act-contact { font-size: 11.5px; }
.act-content { font-size: 13px; color: var(--crm-fg-1); line-height: 1.6; margin-top: 3px; word-break: break-word; }
.act-next {
  display: inline-block; margin-top: 6px;
  font-size: 11.5px; color: var(--crm-amber-500);
  padding: 2px 8px; border-radius: var(--crm-radius-sm);
  background: var(--crm-amber-50);
}
.list-empty { padding: 18px 0; text-align: center; font-size: 12.5px; }

/* 阶段记录 */
.stage-rec-list { display: flex; flex-direction: column; gap: 8px; }
.stage-rec { display: flex; align-items: center; gap: 10px; font-size: 12.5px; }
.stage-rec-content { flex: 1; min-width: 0; color: var(--crm-fg-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.stage-rec-time { font-size: 11.5px; }

.sec-count {
  font-style: normal; font-family: var(--crm-font-mono);
  font-size: 11px; font-weight: 500;
  color: var(--crm-fg-3); background: var(--crm-slate-100);
  border-radius: 8px; padding: 0 6px; margin-left: 6px;
  vertical-align: 1px;
}

@media (max-width: 900px) {
  .stage-rail { flex-wrap: nowrap; }
  .stage-node { min-width: 112px; }
}
@media (max-width: 768px) {
  .detail-hero { padding: 16px 18px; gap: 12px; }
  .detail-hero-side { display: none; }
  .detail-body { padding: 16px 18px 0; }
  .opp-board { flex-direction: column; }
  .board-col { max-width: none; width: 100%; }
  .board-col-cards { max-height: none; }
}
</style>
