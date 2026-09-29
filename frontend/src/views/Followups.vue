<template>
  <div class="page">
    <PageHeader title="联络计划" subtitle="按计划推进每一次触达，逾期与今日待办一目了然">
      <template #actions>
        <el-button :icon="Download" plain @click="doExport">导出</el-button>
        <el-button type="primary" :icon="Plus" @click="openForm()">新增计划</el-button>
      </template>
    </PageHeader>

    <!-- 状态分段 -->
    <div class="tabs-bar">
      <div class="seg-group" role="tablist">
        <button
          v-for="s in STATUS_TABS" :key="s.key"
          class="seg-btn" :class="{ 'is-active': (filter.status || 'all') === s.key }"
          @click="setStatus(s.key)"
        >
          <span class="seg-label">{{ s.label }}</span>
          <span class="seg-count">{{ s.count }}</span>
        </button>
      </div>
      <div v-if="overdueCount" class="overdue-hint">
        <span class="od-dot"></span>{{ overdueCount }} 条已逾期
      </div>
    </div>

    <FilterBar @search="applyFilter" @reset="resetFilter">
      <el-form-item label="内容/客户">
        <el-input v-model="draft.q" placeholder="搜索计划内容或客户..." clearable style="width:200px" @keyup.enter="applyFilter" />
      </el-form-item>
      <el-form-item label="客户">
        <el-select v-model="draft.customer" clearable filterable placeholder="全部客户" style="width:170px" @change="applyFilter">
          <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
        </el-select>
      </el-form-item>
      <el-form-item label="联系人">
        <el-select v-model="draft.contact" clearable filterable placeholder="全部联系人" style="width:150px" @change="applyFilter">
          <el-option v-for="c in dict.contacts" :key="c.id" :value="c.id" :label="c.name" />
        </el-select>
      </el-form-item>
      <el-form-item label="计划从">
        <el-date-picker v-model="draft.from" type="date" value-format="YYYY-MM-DD" placeholder="起始" style="width:150px" />
      </el-form-item>
      <el-form-item label="计划至">
        <el-date-picker v-model="draft.to" type="date" value-format="YYYY-MM-DD" placeholder="结束" style="width:150px" />
      </el-form-item>
    </FilterBar>

    <div class="table-wrap">
      <PageTable
        storage-key="followup" :data="filteredList" :loading="loading"
        :row-class-name="fuRowClass"
        :default-sort="{ prop: 'plan_date', order: 'ascending' }"
        :empty-text="emptyText" empty-hint="把要跟进的人和事写成计划，到期就在这里提醒你"
      >
        <template #empty-action>
          <el-button type="primary" plain size="small" :icon="Plus" @click="openForm()" style="margin-top:12px">新增计划</el-button>
        </template>

        <el-table-column prop="id" label="编号" width="86" sortable="custom">
          <template #default="{ row }">
            <span class="mono serial">{{ fuNo(row.id) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="plan_date" label="计划日期" width="118" sortable="custom">
          <template #default="{ row }">
            <span v-if="row.plan_date" class="mono date" :class="dateClass(row)">
              {{ fmtDateMDY(row.plan_date) }}
            </span>
            <span v-else class="mono dim">—</span>
            <div v-if="!row.actual_date && dateTagText(row)" class="date-tag" :class="dateClass(row)">{{ dateTagText(row) }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="customer_name" label="客户 / 联系人" min-width="180" sortable="custom">
          <template #default="{ row }">
            <div class="cell-title-text" :title="row.customer_name">{{ row.customer_name || '—' }}</div>
            <div v-if="row.contact_name" class="cell-meta">{{ row.contact_name }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="opportunity_title" label="关联商机" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.opportunity_title" class="opp-chip">{{ row.opportunity_title }}</span>
            <span v-else class="dim">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="计划内容" min-width="240" sortable="custom">
          <template #default="{ row }">
            <div class="content-cell" :title="row.content">{{ row.content || '—' }}</div>
            <div v-if="row.actual_content" class="content-done muted">实际：{{ row.actual_content }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="actual_date" label="状态" width="110" sortable="custom">
          <template #default="{ row }">
            <span class="status-pill" :class="row.actual_date ? 'status-pill--done' : 'status-pill--pending'">
              <i class="status-indicator"></i>{{ row.actual_date ? '已完成' : '待联络' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right" align="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button link type="primary" size="small" @click="viewDetail(row.id)">详情</el-button>
              <el-button v-if="!row.actual_date" link type="success" size="small" @click="openExecute(row.id)">联络</el-button>
              <el-dropdown trigger="click" @command="cmd => rowMenu(cmd, row)">
                <el-button link size="small" :icon="MoreFilled" class="row-more" />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="edit">编辑</el-dropdown-item>
                    <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
      </PageTable>
    </div>

    <!-- 新增 / 编辑计划 -->
    <el-dialog v-model="formVisible" :title="editId ? '编辑联系计划' : '新增联系计划'" width="680px" destroy-on-close class="form-dialog">
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="108px" label-position="right">
        <div class="form-section">
          <div class="section-title">时间与对象</div>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="计划日期" prop="plan_date">
                <el-date-picker v-model="form.plan_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="客户">
                <div class="inline-select">
                  <el-select v-model="form.customer_id" clearable filterable placeholder="从客户库选择" style="flex:1" @change="form.contact_id = null">
                    <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
                  </el-select>
                  <el-button title="快速新增客户" @click="qcCustomer.open()">
                    <el-icon><Plus /></el-icon>
                  </el-button>
                </div>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="联系人">
                <div class="inline-select">
                  <el-select v-model="form.contact_id" clearable filterable placeholder="先选客户再选联系人" style="flex:1">
                    <el-option v-for="c in dict.contactsOf(form.customer_id)" :key="c.id" :value="c.id" :label="c.name" />
                  </el-select>
                  <el-button title="快速新增联系人" @click="qcContact.open()">
                    <el-icon><Plus /></el-icon>
                  </el-button>
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="关联商机">
                <el-select v-model="form.opportunity_id" clearable filterable placeholder="选填" style="width:100%">
                  <el-option v-for="o in dict.opportunities" :key="o.id" :value="o.id" :label="o.title" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <div class="form-section">
          <div class="section-title">计划内容</div>
          <el-form-item label="要做什么" prop="content">
            <el-input v-model="form.content" type="textarea" :rows="3" placeholder="如：电话确认投标材料准备进度，敲定现场勘查时间" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingForm" @click="saveForm">{{ editId ? '保存修改' : '创建计划' }}</el-button>
      </template>
    </el-dialog>

    <!-- 计划详情 -->
    <el-dialog v-model="detailVisible" title="联系计划详情" width="720px" destroy-on-close class="detail-dialog">
      <div v-loading="detailLoading" class="detail-loading-wrap">
        <template v-if="detail">
          <div class="detail-hero">
            <div class="detail-hero-body">
              <div class="detail-hero-title">{{ detail.customer_name || '未关联客户' }}</div>
              <div class="detail-hero-meta">
                <span class="mono hero-serial">{{ fuNo(detail.id) }}</span>
                <span class="mono hero-date">{{ fmtDate(detail.plan_date) || '—' }}</span>
                <span v-if="detail.contact_name" class="hero-chip">{{ detail.contact_name }}</span>
                <span class="status-pill" :class="detail.actual_date ? 'status-pill--done' : 'status-pill--pending'">
                  <i class="status-indicator"></i>{{ detail.actual_date ? '已完成 · ' + fmtDate(detail.actual_date) : '待联络' }}
                </span>
              </div>
            </div>
          </div>
          <div class="detail-body">
            <DetailGrid :items="[
              { label: '关联商机', value: detail.opportunity_title || '' },
              { label: '计划日期', value: fmtDate(detail.plan_date) || '', mono: true },
            ]" dense />

            <div class="section-title">本次计划联系内容</div>
            <div class="content-block">{{ detail.content || '—' }}</div>

            <template v-if="detail.actual_content">
              <div class="section-title">本次实际联系内容</div>
              <div class="content-block content-block--ok">{{ detail.actual_content }}</div>
            </template>

            <div class="section-title">之前的联系记录<i v-if="(detail.history || []).length" class="sec-count">{{ detail.history.length }}</i></div>
            <div v-if="(detail.history || []).length" class="act-list">
              <div v-for="(h, i) in detail.history" :key="i" class="act-item">
                <span class="act-rail-dot" :class="{ 'is-first': i === 0 }"></span>
                <div class="act-body">
                  <div class="act-head">
                    <span class="act-time mono">{{ fmtDate(h.time) || '—' }}</span>
                    <span v-if="h.method" class="act-method">{{ h.method }}</span>
                    <span v-if="h.contact_name" class="muted act-contact">{{ h.contact_name }}</span>
                  </div>
                  <div class="act-content">{{ h.content }}</div>
                  <div v-if="h.next_followup_time" class="act-next">预计下次 {{ fmtDate(h.next_followup_time) }}</div>
                </div>
              </div>
            </div>
            <div v-else class="list-empty muted">暂无历史联系记录</div>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button
          v-if="detail && !detail.actual_date" type="primary"
          @click="() => { const id = detail.id; detailVisible = false; openExecute(id) }"
        >执行联络</el-button>
      </template>
    </el-dialog>

    <!-- 执行联络 -->
    <el-dialog
      v-model="execVisible"
      :title="execTarget ? `执行联络 · ${execTarget.customer_name || ''} ${execTarget.contact_name || ''}` : '执行联络'"
      width="640px" destroy-on-close class="form-dialog"
    >
      <template v-if="execTarget">
        <div class="exec-plan">
          <div class="exec-plan-label">计划内容</div>
          <div class="exec-plan-text">{{ execTarget.content || '—' }}</div>
        </div>
        <el-form ref="execFormRef" :model="execForm" :rules="execRules" label-width="112px" label-position="right">
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="联系方式">
                <el-select v-model="execForm.method" style="width:100%">
                  <el-option v-for="m in METHOD_OPTIONS" :key="m" :value="m" :label="m" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="下次联系时间">
                <el-date-picker v-model="execForm.next_time" type="date" value-format="YYYY-MM-DD" style="width:100%" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="本次联系内容" prop="actual_content">
            <el-input v-model="execForm.actual_content" type="textarea" :rows="3" placeholder="记录本次实际沟通内容，将同步到日常联络" />
          </el-form-item>
          <el-form-item label="预计下次内容">
            <el-input v-model="execForm.next_content" />
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="execVisible = false">取消</el-button>
        <el-button type="primary" :loading="execSaving" @click="submitExecute">提交联络</el-button>
      </template>
    </el-dialog>

    <QuickCreateCustomer ref="qcCustomer" :customer-name="customerNameOf(form.customer_id)" @created="c => form.customer_id = c.id" />
    <QuickCreateContact ref="qcContact" :customer-id="form.customer_id" :customer-name="customerNameOf(form.customer_id)" @created="c => form.contact_id = c.id" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Download, MoreFilled } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'
import PageTable from '../components/PageTable.vue'
import FilterBar from '../components/FilterBar.vue'
import QuickCreateCustomer from '../components/QuickCreateCustomer.vue'
import QuickCreateContact from '../components/QuickCreateContact.vue'
import DetailGrid from '../components/DetailGrid.vue'
import { get, getList, post, put, del, fmtDate, fmtDateMDY, exportCsv, METHOD_OPTIONS } from '../api'
import { useFilterMemory } from '../composables/useFilterMemory'
import { useDictStore } from '../stores/app'

const dict = useDictStore()
const route = useRoute()
const qcCustomer = ref(null)
const qcContact = ref(null)
const customerNameOf = (id) => (dict.customers.find((c) => c.id === id) || {}).name || ''
const followups = ref([])
const loading = ref(false)
const fuNo = (id) => (id === null || id === undefined ? '—' : String(id).padStart(6, '0'))
const filter = useFilterMemory('followups', { q: '', customer: '', contact: '', status: '', from: '', to: '' })
const draft = reactive({ q: '', customer: '', contact: '', status: '', from: '', to: '' })

const todayStr = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
const pendingCount = computed(() => followups.value.filter((f) => !f.actual_date).length)
const doneCount = computed(() => followups.value.length - pendingCount.value)
const overdueCount = computed(() => {
  const t = todayStr()
  return followups.value.filter((f) => !f.actual_date && f.plan_date && fmtDate(f.plan_date) < t).length
})
const STATUS_TABS = computed(() => [
  { key: 'all', label: '全部', count: followups.value.length },
  { key: 'pending', label: '待联络', count: pendingCount.value },
  { key: 'done', label: '已完成', count: doneCount.value },
])
const emptyText = computed(() => ({ all: '暂无联络计划', pending: '没有待联络的计划', done: '还没有已完成的计划' }[filter.status || 'all']))

function setStatus(k) {
  draft.status = k === 'all' ? '' : k
  applyFilter()
}

// 日期紧急度：逾期 rose / 今日 amber / 3天内 pine
function dateClass(row) {
  if (row.actual_date || !row.plan_date) return ''
  const pd = fmtDate(row.plan_date), t = todayStr()
  if (pd < t) return 'is-overdue'
  if (pd === t) return 'is-today'
  const d3 = new Date(); d3.setDate(d3.getDate() + 3)
  const d3s = `${d3.getFullYear()}-${String(d3.getMonth() + 1).padStart(2, '0')}-${String(d3.getDate()).padStart(2, '0')}`
  if (pd <= d3s) return 'is-soon'
  return ''
}
function dateTagText(row) {
  const c = dateClass(row)
  return { 'is-overdue': '已逾期', 'is-today': '今日', 'is-soon': '即将' }[c] || ''
}
// #8 待联络且已逾期 → 整行文字标红
function fuRowClass({ row }) {
  return (!row.actual_date && dateClass(row) === 'is-overdue') ? 'row-overdue' : ''
}

const filteredList = computed(() => followups.value.filter((f) => {
  if (filter.q && !((f.content || '').toLowerCase().includes(filter.q.toLowerCase()) || (f.customer_name || '').includes(filter.q))) return false
  if (filter.customer && String(f.customer_id) !== String(filter.customer)) return false
  if (filter.contact && String(f.contact_id) !== String(filter.contact)) return false
  if (filter.status === 'pending' && f.actual_date) return false
  if (filter.status === 'done' && !f.actual_date) return false
  const pd = fmtDate(f.plan_date)
  if (filter.from && pd && pd < filter.from) return false
  if (filter.to && pd && pd > filter.to) return false
  return true
}))

async function load() {
  loading.value = true
  followups.value = await getList('/followups')
  loading.value = false
}
function applyFilter() { Object.assign(filter, draft) }
function resetFilter() {
  Object.assign(draft, { q: '', customer: '', contact: '', status: '', from: '', to: '' })
  Object.assign(filter, draft)
}

// ---- 行内「更多」菜单：把编辑/删除收纳起来，操作列只保留主操作 ----
function rowMenu(cmd, row) {
  if (cmd === 'edit') openForm(row.id)
  else if (cmd === 'delete') deleteFollowup(row.id)
}

// ---- 新增 / 编辑 ----
const formVisible = ref(false)
const editId = ref(null)
const formRef = ref(null)
const savingForm = ref(false)
const form = reactive({})
const formRules = {
  plan_date: [{ required: true, message: '请选择计划日期', trigger: 'change' }],
  content: [{ required: true, message: '请输入计划联系内容', trigger: 'blur' }],
}

function openForm(id) {
  editId.value = id || null
  Object.keys(form).forEach((k) => delete form[k])
  Object.assign(form, { plan_date: '', content: '', customer_id: null, contact_id: null, opportunity_id: null })
  if (id) {
    get(`/followups/${id}`).then((f) => {
      Object.assign(form, {
        plan_date: fmtDate(f.plan_date) || '', content: f.content || '',
        customer_id: f.customer_id, contact_id: f.contact_id, opportunity_id: f.opportunity_id,
      })
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
    const r = editId.value ? await put(`/followups/${editId.value}`, form) : await post('/followups', form)
    if (r.error) return ElMessage.error(r.error)
    ElMessage.success(editId.value ? '更新成功' : '创建成功')
    formVisible.value = false
    load()
  } finally {
    savingForm.value = false
  }
}

// ---- 详情 ----
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref(null)
async function viewDetail(id) {
  const r = await get(`/followups/${id}`)
  if (!r || r.error) return ElMessage.error('加载计划详情失败：' + ((r && r.error) || '请稍后重试'))
  detail.value = r
  detailVisible.value = true
}

// ---- 执行联络 ----
const execVisible = ref(false)
const execTarget = ref(null)
const execId = ref(null)
const execFormRef = ref(null)
const execSaving = ref(false)
const execForm = reactive({ method: '电话', next_time: '', actual_content: '', next_content: '' })
const execRules = { actual_content: [{ required: true, message: '请填写本次联系内容', trigger: 'blur' }] }

async function openExecute(id) {
  const r = await get(`/followups/${id}`)
  if (!r || r.error) return ElMessage.error('加载计划失败：' + ((r && r.error) || '请稍后重试'))
  execTarget.value = r
  execId.value = id
  Object.assign(execForm, { method: '电话', next_time: '', actual_content: '', next_content: '' })
  execVisible.value = true
  nextTick(() => execFormRef.value?.clearValidate())
}

async function submitExecute() {
  if (!execFormRef.value) return
  const valid = await execFormRef.value.validate().catch(() => false)
  if (!valid) return
  execSaving.value = true
  try {
    const r = await post(`/followups/${execId.value}/execute`, { ...execForm })
    if (r.error) return ElMessage.error(r.error)
    ElMessage.success(r.message || '已记录')
    execVisible.value = false
    load()
  } finally {
    execSaving.value = false
  }
}

async function deleteFollowup(id) {
  try {
    await ElMessageBox.confirm('确认删除该计划？', '删除计划', { type: 'warning' })
  } catch (e) { return }
  const r = await del(`/followups/${id}`)
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success('已删除'); load()
}

async function doExport() {
  const err = await exportCsv('followups', filteredList.value)
  err ? ElMessage.error(err) : ElMessage.success(`已导出 ${filteredList.value.length} 条`)
}

onMounted(async () => {
  await Promise.all([load(), dict.loadCustomers(), dict.loadContacts(), dict.loadOpportunities()])
  // 工作台"今日联络计划"直达：?execute=<id> 直接打开执行联络弹窗
  if (route.query.execute) openExecute(Number(route.query.execute))
})
</script>

<style scoped>
/* ---- 状态分段 ---- */
.tabs-bar {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; margin-bottom: 12px; flex-wrap: wrap;
}
.seg-group {
  display: inline-flex; padding: 4px; gap: 2px;
  background: var(--crm-slate-100);
  border-radius: 10px;
  border: 1px solid var(--crm-border-soft);
}
.seg-btn {
  display: inline-flex; align-items: center; gap: 7px;
  padding: 7px 18px; height: 38px;
  border: none; background: transparent; cursor: pointer;
  font-family: inherit; font-size: 15px; font-weight: 600;
  color: var(--crm-fg-3);
  border-radius: 8px;
  transition: all var(--crm-dur-fast) var(--crm-ease-out);
}
.seg-btn:hover { color: var(--crm-fg-1); }
.seg-btn.is-active {
  background: var(--crm-bg-card); color: var(--crm-pine-600);
  box-shadow: var(--crm-shadow-sm);
  font-weight: 700;
}
.seg-count {
  font-family: var(--crm-font-mono); font-size: 12.5px; font-weight: 600;
  padding: 1px 7px; height: 19px; line-height: 17px;
  background: var(--crm-slate-200); color: var(--crm-fg-3);
  border-radius: 10px; min-width: 24px;
}
.seg-btn.is-active .seg-count { background: var(--crm-pine-100); color: var(--crm-pine-600); }
.overdue-hint {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--crm-rose-500); font-weight: 500;
}
.od-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--crm-rose-500); }

/* ---- 表格 ---- */
.table-wrap {
  background: var(--crm-bg-card);
  border: 1px solid var(--crm-border-soft);
  border-radius: var(--crm-radius-lg);
  overflow: hidden;
  box-shadow: var(--crm-shadow-xs);
}
.cell-title-text {
  color: var(--crm-fg-1); font-weight: 500; font-size: 13.5px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.serial { font-size: 12px; color: var(--crm-fg-3); letter-spacing: 0.01em; }
.hero-serial {
  padding: 1px 8px; border-radius: var(--crm-radius-sm);
  background: var(--crm-slate-100); color: var(--crm-fg-2); font-size: 12px;
}
.cell-meta { font-size: 11.5px; color: var(--crm-fg-3); margin-top: 2px; }
.date { font-size: 12.5px; }
.date.is-overdue { color: var(--crm-rose-500); font-weight: 600; }
.date.is-today { color: var(--crm-amber-500); font-weight: 600; }
.date.is-soon { color: var(--crm-pine-600); font-weight: 500; }
.table-wrap :deep(.el-table__row.row-overdue .cell) { color: var(--crm-rose-500); }
.table-wrap :deep(.el-table__row.row-overdue .cell-title-text) { color: var(--crm-rose-500); font-weight: 600; }
.date-tag {
  font-size: 10.5px; line-height: 14px; padding: 0 5px; margin-top: 2px;
  border-radius: 4px; display: inline-block; font-weight: 500;
}
.date-tag.is-overdue { background: var(--crm-rose-50, #fef2f2); color: var(--crm-rose-500); }
.date-tag.is-today { background: var(--crm-amber-50); color: var(--crm-amber-500); }
.date-tag.is-soon { background: var(--crm-pine-25); color: var(--crm-pine-600); }
.opp-chip {
  display: inline-block; max-width: 100%;
  padding: 1px 8px; font-size: 11.5px;
  background: var(--crm-slate-100); color: var(--crm-fg-2);
  border-radius: var(--crm-radius-sm);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.content-cell {
  font-size: 13px; color: var(--crm-fg-1); line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.content-done { font-size: 11.5px; margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.row-actions { display: inline-flex; gap: 0; justify-content: flex-end; align-items: center; }
.row-actions :deep(.el-button.is-link) { padding: 2px 6px; }
.row-more { padding: 0 4px; }

.status-pill {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 2px 8px 2px 6px;
  font-size: 11.5px; font-weight: 500;
  border-radius: var(--crm-radius-full);
  background: var(--crm-slate-100); color: var(--crm-fg-2);
  white-space: nowrap;
}
.status-indicator { width: 6px; height: 6px; border-radius: 50%; background: currentColor; opacity: 0.9; }
.status-pill--pending { background: var(--crm-sky-50); color: var(--crm-sky-500); }
.status-pill--done { background: var(--crm-pine-25); color: var(--crm-pine-600); }

/* ---- 表单分组 ---- */
.form-section { margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px dashed var(--crm-border-soft); }
.form-section:last-child { margin-bottom: 0; padding-bottom: 0; border-bottom: none; }

/* ---- 详情弹窗 ---- */
.detail-dialog :deep(.el-dialog__body) { padding: 0 !important; }
.detail-loading-wrap { min-height: 120px; }
.detail-hero {
  display: flex; align-items: center; gap: 14px;
  padding: 20px 24px 18px;
  background: linear-gradient(180deg, var(--crm-pine-25) 0%, var(--crm-bg-card) 100%);
  border-bottom: 1px solid var(--crm-border-soft);
}
.detail-hero-body { flex: 1; min-width: 0; }
.detail-hero-title {
  font-family: var(--crm-font-display);
  font-size: 16px; font-weight: 600; color: var(--crm-fg-1);
  line-height: 1.4; letter-spacing: -0.011em;
  margin-bottom: 6px; word-break: break-word;
}
.detail-hero-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 12px; color: var(--crm-fg-3); }
.hero-date { font-size: 12.5px; color: var(--crm-fg-2); font-weight: 500; }
.hero-chip {
  padding: 1px 8px; border-radius: var(--crm-radius-sm);
  background: var(--crm-slate-100); color: var(--crm-fg-2); font-size: 12px;
}
.detail-body { padding: 18px 24px 8px; }

.content-block {
  font-size: 13.5px; line-height: 1.8; white-space: pre-wrap; word-break: break-word;
  background: var(--crm-slate-25);
  border: 1px solid var(--crm-border-soft);
  border-radius: var(--crm-radius-md);
  padding: 12px 14px;
}
.content-block--ok { background: var(--crm-pine-25); border-color: var(--crm-pine-100); }

/* 历史时间轴 */
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
.list-empty { padding: 22px 0; text-align: center; font-size: 12.5px; }
.sec-count {
  font-style: normal; font-family: var(--crm-font-mono);
  font-size: 11px; font-weight: 500;
  color: var(--crm-fg-3); background: var(--crm-slate-100);
  border-radius: 8px; padding: 0 6px; margin-left: 6px;
  vertical-align: 1px;
}

/* ---- 执行联络 ---- */
.exec-plan {
  padding: 12px 14px; margin-bottom: 16px;
  background: var(--crm-sky-50);
  border: 1px solid var(--crm-sky-50, #eaf4fb);
  border-radius: var(--crm-radius-md);
}
.exec-plan-label { font-size: 11px; font-weight: 600; color: var(--crm-sky-500); letter-spacing: 0.04em; margin-bottom: 4px; }
.exec-plan-text { font-size: 13px; color: var(--crm-fg-1); line-height: 1.6; }

@media (max-width: 768px) {
  .detail-hero { padding: 16px 18px; }
  .detail-body { padding: 16px 18px 0; }
}
</style>
