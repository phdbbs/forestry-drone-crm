<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">联络计划</h2>
      <div class="page-toolbar">
        <el-button @click="doExport"><el-icon><Download /></el-icon>&nbsp;导出</el-button>
        <el-button type="primary" @click="openForm()"><el-icon><Plus /></el-icon>&nbsp;新增联系计划</el-button>
      </div>
    </div>

    <FilterBar @search="applyFilter" @reset="resetFilter">
      <el-form-item label="内容/客户">
        <el-input v-model="draft.q" placeholder="搜索计划内容或客户..." clearable style="width:180px" />
      </el-form-item>
      <el-form-item label="客户">
        <el-select v-model="draft.customer" clearable filterable style="width:160px" @change="applyFilter">
          <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
        </el-select>
      </el-form-item>
      <el-form-item label="联系人">
        <el-select v-model="draft.contact" clearable filterable style="width:140px" @change="applyFilter">
          <el-option v-for="c in dict.contacts" :key="c.id" :value="c.id" :label="c.name" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="draft.status" clearable style="width:120px" @change="applyFilter">
          <el-option value="pending" label="待联络" />
          <el-option value="done" label="已完成" />
        </el-select>
      </el-form-item>
      <el-form-item label="计划从">
        <el-date-picker v-model="draft.from" type="date" value-format="YYYY-MM-DD" style="width:140px" />
      </el-form-item>
      <el-form-item label="至">
        <el-date-picker v-model="draft.to" type="date" value-format="YYYY-MM-DD" style="width:140px" />
      </el-form-item>
    </FilterBar>

    <el-card shadow="never" body-style="padding:0">
      <PageTable storage-key="followup" :data="filteredList" :loading="loading" :default-sort="{ prop: 'plan_date', order: 'ascending' }">
        <el-table-column prop="plan_date" label="计划日期" width="110" sortable="custom">
          <template #default="{ row }">{{ fmtDate(row.plan_date) || '-' }}</template>
        </el-table-column>
        <el-table-column prop="customer_name" label="客户" min-width="150" sortable="custom" show-overflow-tooltip />
        <el-table-column prop="contact_name" label="联系人" width="110" sortable="custom" />
        <el-table-column prop="opportunity_title" label="关联商机" min-width="130" show-overflow-tooltip />
        <el-table-column prop="content" label="计划内容" min-width="200" sortable="custom" show-overflow-tooltip />
        <el-table-column prop="actual_date" label="状态" width="90" sortable="custom">
          <template #default="{ row }">
            <el-tag size="small" :type="row.actual_date ? 'success' : 'primary'">{{ row.actual_date ? '已完成' : '待联络' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="230" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewDetail(row.id)">详情</el-button>
            <el-button v-if="!row.actual_date" link type="success" size="small" @click="openExecute(row.id)">联络</el-button>
            <el-button link type="primary" size="small" @click="openForm(row.id)">编辑</el-button>
            <el-button link type="danger" size="small" @click="deleteFollowup(row.id)"><el-icon><Delete /></el-icon></el-button>
          </template>
        </el-table-column>
      </PageTable>
    </el-card>

    <!-- 新增/编辑计划 -->
    <el-dialog v-model="formVisible" :title="editId ? '编辑联系计划' : '新增联系计划'" width="600px" destroy-on-close>
      <el-form :model="form" label-width="110px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="计划日期">
              <el-date-picker v-model="form.plan_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户">
              <el-select v-model="form.customer_id" clearable filterable style="width:100%" @change="form.contact_id = null">
                <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="联系人">
              <el-select v-model="form.contact_id" clearable filterable style="width:100%">
                <el-option v-for="c in dict.contactsOf(form.customer_id)" :key="c.id" :value="c.id" :label="c.name" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联商机">
              <el-select v-model="form.opportunity_id" clearable filterable style="width:100%">
                <el-option v-for="o in dict.opportunities" :key="o.id" :value="o.id" :label="o.title" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="计划联系内容" required><el-input v-model="form.content" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" @click="saveForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 计划详情 -->
    <el-dialog v-model="detailVisible" title="联系计划详情" width="640px" destroy-on-close>
      <template v-if="detail">
        <DetailGrid :items="[
          { label: '计划日期', value: fmtDate(detail.plan_date) || '-' },
          { label: '状态', value: detail.actual_date ? `已完成 (${fmtDate(detail.actual_date)})` : '待联络' },
          { label: '客户', value: detail.customer_name },
          { label: '联系人', value: detail.contact_name },
          { label: '关联商机', value: detail.opportunity_title || '无' },
        ]" style="margin-bottom:12px" />
        <div style="font-weight:600;font-size:13px;margin-bottom:6px">本次计划联系内容</div>
        <div style="font-size:14px;background:#f8fafc;border-radius:8px;padding:10px 12px;margin-bottom:14px">{{ detail.content || '-' }}</div>
        <template v-if="detail.actual_content">
          <div style="font-weight:600;font-size:13px;margin-bottom:6px">本次实际联系内容</div>
          <div style="font-size:14px;background:var(--crm-primary-bg);border-radius:8px;padding:10px 12px;margin-bottom:14px">{{ detail.actual_content }}</div>
        </template>
        <div style="font-weight:600;font-size:13px;margin-bottom:8px">之前的联系记录</div>
        <el-timeline v-if="(detail.history || []).length" style="padding-left:4px">
          <el-timeline-item v-for="(h, i) in detail.history" :key="i" :timestamp="`${fmtDate(h.time) || ''} ${h.method || ''}`">
            {{ h.content }}
            <span v-if="h.contact_name" class="muted">（{{ h.contact_name }}）</span>
            <div v-if="h.next_followup_time" style="color:var(--el-color-warning);font-size:12px">预计下次: {{ fmtDate(h.next_followup_time) }}</div>
          </el-timeline-item>
        </el-timeline>
        <div v-else class="muted">暂无历史联系记录</div>
      </template>
      <template #footer><el-button @click="detailVisible = false">关闭</el-button></template>
    </el-dialog>

    <!-- 执行联络 -->
    <el-dialog v-model="execVisible" :title="execTarget ? `执行联络 · ${execTarget.customer_name || ''} ${execTarget.contact_name || ''}` : '执行联络'" width="560px" destroy-on-close>
      <template v-if="execTarget">
        <div class="muted" style="background:#f8fafc;border-radius:8px;padding:10px 12px;margin-bottom:12px">计划内容：{{ execTarget.content }}</div>
        <el-form :model="execForm" label-width="120px">
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
          <el-form-item label="本次联系内容" required>
            <el-input v-model="execForm.actual_content" type="textarea" :rows="3" placeholder="记录本次实际沟通内容，将同步到日常联络" />
          </el-form-item>
          <el-form-item label="预计下次内容"><el-input v-model="execForm.next_content" /></el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="execVisible = false">取消</el-button>
        <el-button type="primary" @click="submitExecute">提交联络</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Download, Delete } from '@element-plus/icons-vue'
import PageTable from '../components/PageTable.vue'
import FilterBar from '../components/FilterBar.vue'
import DetailGrid from '../components/DetailGrid.vue'
import { get, post, put, del, fmtDate, exportCsv, METHOD_OPTIONS } from '../api'
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
  followups.value = (await get('/followups')) || []
  loading.value = false
}
function applyFilter() { Object.assign(filter, draft) }
function resetFilter() {
  Object.assign(draft, { q: '', customer: '', contact: '', status: '', from: '', to: '' })
  Object.assign(filter, draft)
}

// ---- 新增/编辑 ----
const formVisible = ref(false)
const editId = ref(null)
const form = reactive({})
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
}
async function saveForm() {
  if (!form.content) return ElMessage.error('请输入内容')
  const r = editId.value ? await put(`/followups/${editId.value}`, form) : await post('/followups', form)
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success(editId.value ? '更新成功' : '创建成功')
  formVisible.value = false
  load()
}

// ---- 详情 ----
const detailVisible = ref(false)
const detail = ref(null)
async function viewDetail(id) {
  detail.value = await get(`/followups/${id}`)
  detailVisible.value = true
}

// ---- 执行联络 ----
const execVisible = ref(false)
const execTarget = ref(null)
const execId = ref(null)
const execForm = reactive({ method: '电话', next_time: '', actual_content: '', next_content: '' })
async function openExecute(id) {
  execTarget.value = await get(`/followups/${id}`)
  execId.value = id
  Object.assign(execForm, { method: '电话', next_time: '', actual_content: '', next_content: '' })
  execVisible.value = true
}
async function submitExecute() {
  if (!execForm.actual_content) return ElMessage.error('请填写本次联系内容')
  const r = await post(`/followups/${execId.value}/execute`, { ...execForm })
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success(r.message || '已记录')
  execVisible.value = false
  load()
}
async function deleteFollowup(id) {
  await ElMessageBox.confirm('确认删除该计划？', '删除计划')
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
