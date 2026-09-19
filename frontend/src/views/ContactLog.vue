<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">日常联络</h2>
      <div class="page-toolbar">
        <el-button :icon="Download" @click="doExport">导出</el-button>
        <el-button type="primary" :icon="Plus" @click="openForm()">新增日常联络</el-button>
      </div>
    </div>

    <FilterBar @search="applyFilter" @reset="resetFilter">
      <el-form-item label="开始日期">
        <el-date-picker v-model="draft.date_from" type="date" value-format="YYYY-MM-DD" class="w-140" />
      </el-form-item>
      <el-form-item label="结束日期">
        <el-date-picker v-model="draft.date_to" type="date" value-format="YYYY-MM-DD" class="w-140" />
      </el-form-item>
      <el-form-item label="客户">
        <el-select v-model="draft.customer" clearable filterable class="w-170" @change="applyFilter">
          <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
        </el-select>
      </el-form-item>
      <el-form-item label="商机">
        <el-select v-model="draft.opp" clearable filterable class="w-190" @change="applyFilter">
          <el-option v-for="o in dict.opportunities" :key="o.id" :value="o.id" :label="o.title" />
        </el-select>
      </el-form-item>
      <el-form-item label="内容">
        <el-input v-model="draft.q" placeholder="搜索内容..." clearable class="w-170" />
      </el-form-item>
    </FilterBar>

    <el-row :gutter="16" align="top">
      <el-col :xs="24" :lg="16">
        <el-card shadow="never" body-class="p-0">
          <PageTable storage-key="activity" :data="filteredList" :loading="loading" :default-sort="{ prop: 'activity_time', order: 'descending' }">
            <el-table-column prop="activity_time" label="时间" width="110" sortable="custom">
              <template #default="{ row }">{{ fmtDate(row.activity_time) || '-' }}</template>
            </el-table-column>
            <el-table-column prop="customer_name" label="客户" min-width="140" sortable="custom" show-overflow-tooltip class-name="cell-strong" />
            <el-table-column prop="opportunity_title" label="商机" min-width="140" sortable="custom" show-overflow-tooltip />
            <el-table-column prop="contact_name" label="联系人" width="100" sortable="custom" />
            <el-table-column prop="content" label="内容" min-width="200" sortable="custom" show-overflow-tooltip />
            <el-table-column prop="next_followup_time" label="预计联系" width="110" sortable="custom">
              <template #default="{ row }">{{ fmtDate(row.next_followup_time) || '-' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="140" fixed="right" align="center">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="viewDetail(row.id)">查看</el-button>
                <el-button link type="primary" size="small" @click="openForm(row.id)">编辑</el-button>
                <el-button link type="danger" size="small" @click="deleteActivity(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </PageTable>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="8">
        <el-card shadow="never" class="stat-panel">
          <template #header>
            <div class="panel-head">
              <el-icon><TrendCharts /></el-icon>
              <span>联络统计</span>
            </div>
          </template>
          <div class="stat-item">
            <el-statistic title="总联络记录" :value="allCount" suffix="次" />
          </div>
          <el-divider />
          <div class="stat-item">
            <el-statistic title="当前筛选结果" :value="filteredList.length" suffix="条" />
          </div>
          <el-divider />
          <div class="stat-item">
            <el-statistic title="涉及客户" :value="customerCount" suffix="家" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 新增 / 编辑联络 -->
    <el-dialog v-model="formVisible" :title="editId ? '编辑联络记录' : '新增日常联络'" width="640px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="120px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="客户" prop="customer_id">
              <el-select v-model="form.customer_id" clearable filterable class="w-full" @change="form.contact_id = null">
                <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系人">
              <el-select v-model="form.contact_id" clearable filterable class="w-full">
                <el-option v-for="c in dict.contactsOf(form.customer_id)" :key="c.id" :value="c.id" :label="c.name" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="关联商机">
          <el-select v-model="form.opportunity_id" clearable filterable class="w-full">
            <el-option v-for="o in dict.opportunities" :key="o.id" :value="o.id" :label="o.title" />
          </el-select>
          <div class="muted">非必选，可联系客户增进感情或沟通具体商机</div>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="方式" prop="method">
              <el-select v-model="form.method" class="w-full">
                <el-option v-for="m in METHOD_OPTIONS" :key="m" :value="m" :label="m" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="时间" prop="time">
              <el-date-picker v-model="form.time" type="date" value-format="YYYY-MM-DD" class="w-full" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="内容" prop="content">
          <el-input v-model="form.content" type="textarea" :rows="3" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="下次跟进日期">
              <el-date-picker v-model="form.next_time" type="date" value-format="YYYY-MM-DD" class="w-full" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="下次跟进内容">
              <el-input v-model="form.next_content" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingForm" @click="saveForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 详情 -->
    <el-dialog v-model="detailVisible" title="联络记录详情" width="600px" destroy-on-close>
      <div v-loading="detailLoading" class="detail-body">
        <template v-if="detail">
          <DetailGrid :items="[
            { label: '时间', value: fmtDate(detail.activity_time) || '-' },
            { label: '方式', value: detail.method },
            { label: '客户', value: detail.customer_name },
            { label: '联系人', value: detail.contact_name },
            { label: '关联商机', value: detail.opportunity_title || '无' },
            { label: '预计联系', value: fmtDate(detail.next_followup_time) || '-' },
          ]" />
          <el-divider content-position="left">联络内容</el-divider>
          <div class="content-block">{{ detail.content || '-' }}</div>
          <el-alert
            v-if="detail.next_followup_content"
            class="next-alert"
            type="info"
            :closable="false"
            show-icon
            :title="`预计联系内容：${detail.next_followup_content}`"
          />
        </template>
      </div>
      <template #footer><el-button @click="detailVisible = false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Download, TrendCharts } from '@element-plus/icons-vue'
import PageTable from '../components/PageTable.vue'
import FilterBar from '../components/FilterBar.vue'
import DetailGrid from '../components/DetailGrid.vue'
import { get, getList, post, put, del, fmtDate, exportCsv, METHOD_OPTIONS } from '../api'
import { useDictStore } from '../stores/app'

const route = useRoute()
const dict = useDictStore()
const activities = ref([])
const allCount = ref(0)
const loading = ref(false)
const filter = reactive({ date_from: '', date_to: '', customer: '', opp: '', q: '' })
const draft = reactive({ date_from: '', date_to: '', customer: '', opp: '', q: '' })

const filteredList = computed(() => activities.value.filter((a) => {
  const ad = fmtDate(a.activity_time)
  if (filter.date_from && ad && ad < filter.date_from) return false
  if (filter.date_to && ad && ad > filter.date_to) return false
  if (filter.customer && String(a.customer_id) !== String(filter.customer)) return false
  if (filter.opp && String(a.opportunity_id) !== String(filter.opp)) return false
  if (filter.q && !(a.content || '').toLowerCase().includes(filter.q.toLowerCase())) return false
  return true
}))

const customerCount = computed(() => new Set(filteredList.value.map((a) => a.customer_id).filter(Boolean)).size)

async function load() {
  loading.value = true
  const list = await getList('/activities')
  allCount.value = list.length
  activities.value = list
  loading.value = false
}
function applyFilter() { Object.assign(filter, draft) }
function resetFilter() {
  Object.assign(draft, { date_from: '', date_to: '', customer: '', opp: '', q: '' })
  Object.assign(filter, draft)
}

// ---- 新增 / 编辑 ----
const formVisible = ref(false)
const editId = ref(null)
const formRef = ref(null)
const savingForm = ref(false)
const form = reactive({})
const formRules = {
  customer_id: [{ required: true, message: '请选择客户', trigger: 'change' }],
  method: [{ required: true, message: '请选择联络方式', trigger: 'change' }],
  time: [{ required: true, message: '请选择联络时间', trigger: 'change' }],
  content: [{ required: true, message: '请输入联络内容', trigger: 'blur' }],
}

function openForm(id, presets) {
  presets = presets || {}
  editId.value = id || null
  Object.keys(form).forEach((k) => delete form[k])
  Object.assign(form, {
    customer_id: presets.customer_id || null,
    contact_id: null,
    opportunity_id: presets.opportunity_id || null,
    method: '电话', time: '', content: '', next_time: '', next_content: '',
  })
  if (id) {
    get(`/activities/${id}`).then((a) => {
      if (a && a.id) {
        Object.assign(form, {
          customer_id: a.customer_id, contact_id: a.contact_id, opportunity_id: a.opportunity_id,
          method: a.method || '电话', time: fmtDate(a.activity_time) || '', content: a.content || '',
          next_time: fmtDate(a.next_followup_time) || '', next_content: a.next_followup_content || '',
        })
      }
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
    const d = {
      customer_id: form.customer_id || null, contact_id: form.contact_id || null,
      opportunity_id: form.opportunity_id || null, method: form.method, time: form.time || '',
      content: form.content, next_time: form.next_time, next_content: form.next_content,
    }
    const r = editId.value ? await put(`/activities/${editId.value}`, d) : await post('/activities', d)
    if (r.error) return ElMessage.error(r.error)
    ElMessage.success(editId.value ? '更新成功' : '创建成功')
    formVisible.value = false
    load(); dict.loadOpportunities()
  } finally {
    savingForm.value = false
  }
}

async function deleteActivity(id) {
  try {
    await ElMessageBox.confirm('确认删除该联络记录？', '删除记录', { type: 'warning' })
  } catch (e) { return }
  const r = await del(`/activities/${id}`)
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success('已删除'); load()
}

// ---- 详情 ----
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref(null)
async function viewDetail(id) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = await get(`/activities/${id}`)
  detailLoading.value = false
}

async function doExport() {
  const err = await exportCsv('activities', filteredList.value)
  err ? ElMessage.error(err) : ElMessage.success(`已导出 ${filteredList.value.length} 条`)
}

onMounted(async () => {
  await Promise.all([load(), dict.loadCustomers(), dict.loadContacts(), dict.loadOpportunities()])
  // 从商机/客户页跳来时通过路由 query 预填（原先靠 window._presetActivity 全局变量，刷新即丢）
  const { opportunityId, customerId } = route.query
  if (opportunityId || customerId) {
    openForm(null, {
      opportunity_id: opportunityId ? Number(opportunityId) : null,
      customer_id: customerId ? Number(customerId) : null,
    })
  }
})
</script>

<style scoped>
.w-full { width: 100%; }
.w-140 { width: 140px; }
.w-170 { width: 170px; }
.w-190 { width: 190px; }

.stat-panel :deep(.el-card__body) { padding: 20px; }
.panel-head { display: flex; align-items: center; gap: 8px; }
.stat-item { text-align: left; }

.detail-body { min-height: 80px; }
.content-block { font-size: 14px; line-height: 1.8; white-space: pre-wrap; word-break: break-all; }
.next-alert { margin-top: 12px; }
</style>
