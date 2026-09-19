<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">联络计划</h2>
      <div class="page-toolbar">
        <el-button :icon="Download" @click="doExport">导出</el-button>
        <el-button type="primary" :icon="Plus" @click="openForm()">新增联系计划</el-button>
      </div>
    </div>

    <FilterBar @search="applyFilter" @reset="resetFilter">
      <el-form-item label="内容/客户">
        <el-input v-model="draft.q" placeholder="搜索计划内容或客户..." clearable class="w-180" />
      </el-form-item>
      <el-form-item label="客户">
        <el-select v-model="draft.customer" clearable filterable class="w-160" @change="applyFilter">
          <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
        </el-select>
      </el-form-item>
      <el-form-item label="联系人">
        <el-select v-model="draft.contact" clearable filterable class="w-140" @change="applyFilter">
          <el-option v-for="c in dict.contacts" :key="c.id" :value="c.id" :label="c.name" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="draft.status" clearable class="w-120" @change="applyFilter">
          <el-option value="pending" label="待联络" />
          <el-option value="done" label="已完成" />
        </el-select>
      </el-form-item>
      <el-form-item label="计划从">
        <el-date-picker v-model="draft.from" type="date" value-format="YYYY-MM-DD" class="w-140" />
      </el-form-item>
      <el-form-item label="至">
        <el-date-picker v-model="draft.to" type="date" value-format="YYYY-MM-DD" class="w-140" />
      </el-form-item>
    </FilterBar>

    <el-card shadow="never" body-class="p-0">
      <PageTable storage-key="followup" :data="filteredList" :loading="loading" :default-sort="{ prop: 'plan_date', order: 'ascending' }">
        <el-table-column prop="plan_date" label="计划日期" width="110" sortable="custom">
          <template #default="{ row }">{{ fmtDate(row.plan_date) || '-' }}</template>
        </el-table-column>
        <el-table-column prop="customer_name" label="客户" min-width="150" sortable="custom" show-overflow-tooltip class-name="cell-strong" />
        <el-table-column prop="contact_name" label="联系人" width="110" sortable="custom" />
        <el-table-column prop="opportunity_title" label="关联商机" min-width="130" show-overflow-tooltip />
        <el-table-column prop="content" label="计划内容" min-width="200" sortable="custom" show-overflow-tooltip />
        <el-table-column prop="actual_date" label="状态" width="90" sortable="custom" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.actual_date ? 'success' : 'primary'" effect="light">
              {{ row.actual_date ? '已完成' : '待联络' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right" align="center">
          <template #default="{ row }">
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
          </template>
        </el-table-column>
      </PageTable>
    </el-card>

    <!-- 新增 / 编辑计划 -->
    <el-dialog v-model="formVisible" :title="editId ? '编辑联系计划' : '新增联系计划'" width="600px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="110px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="计划日期" prop="plan_date">
              <el-date-picker v-model="form.plan_date" type="date" value-format="YYYY-MM-DD" class="w-full" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户">
              <el-select v-model="form.customer_id" clearable filterable class="w-full" @change="form.contact_id = null">
                <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="联系人">
              <el-select v-model="form.contact_id" clearable filterable class="w-full">
                <el-option v-for="c in dict.contactsOf(form.customer_id)" :key="c.id" :value="c.id" :label="c.name" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联商机">
              <el-select v-model="form.opportunity_id" clearable filterable class="w-full">
                <el-option v-for="o in dict.opportunities" :key="o.id" :value="o.id" :label="o.title" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="计划联系内容" prop="content">
          <el-input v-model="form.content" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingForm" @click="saveForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 计划详情 -->
    <el-dialog v-model="detailVisible" title="联系计划详情" width="640px" destroy-on-close>
      <div v-loading="detailLoading" class="detail-body">
        <template v-if="detail">
          <DetailGrid :items="[
            { label: '计划日期', value: fmtDate(detail.plan_date) || '-' },
            { label: '状态', slot: 'status' },
            { label: '客户', value: detail.customer_name },
            { label: '联系人', value: detail.contact_name },
            { label: '关联商机', value: detail.opportunity_title || '无' },
          ]">
            <template #status>
              <el-tag v-if="detail.actual_date" size="small" type="success" effect="light">
                已完成（{{ fmtDate(detail.actual_date) }}）
              </el-tag>
              <el-tag v-else size="small" effect="light">待联络</el-tag>
            </template>
          </DetailGrid>

          <el-divider content-position="left">本次计划联系内容</el-divider>
          <div class="content-block">{{ detail.content || '-' }}</div>

          <template v-if="detail.actual_content">
            <el-divider content-position="left">本次实际联系内容</el-divider>
            <div class="content-block content-block--ok">{{ detail.actual_content }}</div>
          </template>

          <el-divider content-position="left">之前的联系记录</el-divider>
          <el-timeline v-if="(detail.history || []).length">
            <el-timeline-item v-for="(h, i) in detail.history" :key="i" :timestamp="`${fmtDate(h.time) || ''} ${h.method || ''}`">
              {{ h.content }}
              <span v-if="h.contact_name" class="muted">（{{ h.contact_name }}）</span>
              <div v-if="h.next_followup_time" class="next-hint">预计下次: {{ fmtDate(h.next_followup_time) }}</div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无历史联系记录" :image-size="60" />
        </template>
      </div>
      <template #footer><el-button @click="detailVisible = false">关闭</el-button></template>
    </el-dialog>

    <!-- 执行联络 -->
    <el-dialog
      v-model="execVisible"
      :title="execTarget ? `执行联络 · ${execTarget.customer_name || ''} ${execTarget.contact_name || ''}` : '执行联络'"
      width="560px"
      destroy-on-close
    >
      <template v-if="execTarget">
        <el-alert type="info" :closable="false" show-icon class="exec-plan" :title="`计划内容：${execTarget.content || '-'}`" />
        <el-form ref="execFormRef" :model="execForm" :rules="execRules" label-width="120px">
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="联系方式">
                <el-select v-model="execForm.method" class="w-full">
                  <el-option v-for="m in METHOD_OPTIONS" :key="m" :value="m" :label="m" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="下次联系时间">
                <el-date-picker v-model="execForm.next_time" type="date" value-format="YYYY-MM-DD" class="w-full" />
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
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Download, MoreFilled } from '@element-plus/icons-vue'
import PageTable from '../components/PageTable.vue'
import FilterBar from '../components/FilterBar.vue'
import DetailGrid from '../components/DetailGrid.vue'
import { get, getList, post, put, del, fmtDate, exportCsv, METHOD_OPTIONS } from '../api'
import { useDictStore } from '../stores/app'

const dict = useDictStore()
const followups = ref([])
const loading = ref(false)
const filter = reactive({ q: '', customer: '', contact: '', status: '', from: '', to: '' })
const draft = reactive({ q: '', customer: '', contact: '', status: '', from: '', to: '' })

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
  detailVisible.value = true
  detailLoading.value = true
  detail.value = await get(`/followups/${id}`)
  detailLoading.value = false
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
  execTarget.value = await get(`/followups/${id}`)
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
})
</script>

<style scoped>
.w-full { width: 100%; }
.w-120 { width: 120px; }
.w-140 { width: 140px; }
.w-160 { width: 160px; }
.w-180 { width: 180px; }

.row-more { padding: 0 4px; }
.detail-body { min-height: 80px; }
.content-block {
  font-size: 14px; line-height: 1.8; white-space: pre-wrap; word-break: break-all;
  background: var(--el-fill-color-lighter);
  border-radius: var(--el-border-radius-base);
  padding: 10px 12px;
}
.content-block--ok { background: var(--el-color-primary-light-9); }
.next-hint { color: var(--el-color-warning); font-size: 12px; }
.exec-plan { margin-bottom: 16px; }
</style>
