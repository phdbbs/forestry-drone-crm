<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">日常联络</h2>
      <div class="page-toolbar">
        <el-button @click="doExport"><el-icon><Download /></el-icon>&nbsp;导出</el-button>
        <el-button type="primary" @click="openForm()"><el-icon><Plus /></el-icon>&nbsp;新增日常联络</el-button>
      </div>
    </div>

    <FilterBar @search="applyFilter" @reset="resetFilter">
      <el-form-item label="开始日期">
        <el-date-picker v-model="draft.date_from" type="date" value-format="YYYY-MM-DD" style="width:140px" />
      </el-form-item>
      <el-form-item label="结束日期">
        <el-date-picker v-model="draft.date_to" type="date" value-format="YYYY-MM-DD" style="width:140px" />
      </el-form-item>
      <el-form-item label="客户">
        <el-select v-model="draft.customer" clearable filterable style="width:170px" @change="applyFilter">
          <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
        </el-select>
      </el-form-item>
      <el-form-item label="商机">
        <el-select v-model="draft.opp" clearable filterable style="width:190px" @change="applyFilter">
          <el-option v-for="o in dict.opportunities" :key="o.id" :value="o.id" :label="o.title" />
        </el-select>
      </el-form-item>
      <el-form-item label="内容">
        <el-input v-model="draft.q" placeholder="搜索内容..." clearable style="width:170px" />
      </el-form-item>
    </FilterBar>

    <div style="display:grid;grid-template-columns:2fr 1fr;gap:16px;align-items:start" class="log-grid">
      <el-card shadow="never" body-style="padding:0">
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
              <el-button link type="danger" size="small" @click="deleteActivity(row.id)"><el-icon><Delete /></el-icon></el-button>
            </template>
          </el-table-column>
        </PageTable>
      </el-card>
      <el-card shadow="never" body-style="padding:16px 20px">
        <div style="font-weight:600;margin-bottom:12px">
          <el-icon><TrendCharts /></el-icon>&nbsp;联络统计
        </div>
        <div style="font-size:13px">
          <div style="display:flex;justify-content:space-between;margin-bottom:8px">
            <span class="muted">总联络记录</span><strong>{{ allCount }} 次</strong>
          </div>
          <el-progress :percentage="Math.min(allCount * 10, 100)" :show-text="false" style="margin-bottom:12px" />
          <div style="display:flex;justify-content:space-between;margin-bottom:8px">
            <span class="muted">筛选结果</span><strong>{{ filteredList.length }} 条</strong>
          </div>
          <div class="muted" style="margin-top:8px">联络计划已移至左侧"联络计划"模块</div>
        </div>
      </el-card>
    </div>

    <!-- 新增/编辑联络 -->
    <el-dialog v-model="formVisible" :title="editId ? '编辑联络记录' : '新增日常联络'" width="640px" destroy-on-close>
      <el-form :model="form" label-width="120px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="客户">
              <el-select v-model="form.customer_id" clearable filterable style="width:100%" @change="form.contact_id = null">
                <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系人">
              <el-select v-model="form.contact_id" clearable filterable style="width:100%">
                <el-option v-for="c in dict.contactsOf(form.customer_id)" :key="c.id" :value="c.id" :label="c.name" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="关联商机">
          <el-select v-model="form.opportunity_id" clearable filterable style="width:100%">
            <el-option v-for="o in dict.opportunities" :key="o.id" :value="o.id" :label="o.title" />
          </el-select>
          <div class="muted">非必选，可联系客户增进感情或沟通具体商机</div>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="方式">
              <el-select v-model="form.method" style="width:100%">
                <el-option v-for="m in METHOD_OPTIONS" :key="m" :value="m" :label="m" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="时间">
              <el-date-picker v-model="form.time" type="date" value-format="YYYY-MM-DD" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="内容"><el-input v-model="form.content" type="textarea" :rows="3" /></el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="下次跟进日期">
              <el-date-picker v-model="form.next_time" type="date" value-format="YYYY-MM-DD" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12"><el-form-item label="下次跟进内容"><el-input v-model="form.next_content" /></el-form-item></el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" @click="saveForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 详情 -->
    <el-dialog v-model="detailVisible" title="联络记录详情" width="600px" destroy-on-close>
      <template v-if="detail">
        <DetailGrid :items="[
          { label: '时间', value: fmtDate(detail.activity_time) || '-' },
          { label: '方式', value: detail.method },
          { label: '客户', value: detail.customer_name },
          { label: '联系人', value: detail.contact_name },
          { label: '关联商机', value: detail.opportunity_title || '无' },
          { label: '预计联系', value: fmtDate(detail.next_followup_time) || '-' },
        ]" />
        <div style="margin-top:12px">
          <span class="muted" style="font-size:13px">内容：</span>
          <div style="font-size:14px;margin-top:4px;white-space:pre-wrap">{{ detail.content || '-' }}</div>
        </div>
        <div v-if="detail.next_followup_content" class="muted" style="margin-top:8px">预计联系内容：{{ detail.next_followup_content }}</div>
      </template>
      <template #footer><el-button @click="detailVisible = false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Download, Delete, TrendCharts } from '@element-plus/icons-vue'
import PageTable from '../components/PageTable.vue'
import FilterBar from '../components/FilterBar.vue'
import DetailGrid from '../components/DetailGrid.vue'
import { get, post, put, del, fmtDate, exportCsv, METHOD_OPTIONS } from '../api'
import { useDictStore } from '../stores/app'

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

async function load() {
  loading.value = true
  const list = (await get('/activities')) || []
  allCount.value = list.length
  activities.value = list
  loading.value = false
}
function applyFilter() { Object.assign(filter, draft) }
function resetFilter() {
  Object.assign(draft, { date_from: '', date_to: '', customer: '', opp: '', q: '' })
  Object.assign(filter, draft)
}

// ---- 新增/编辑 ----
const formVisible = ref(false)
const editId = ref(null)
const form = reactive({})
function openForm(id, presets) {
  presets = presets || {}
  editId.value = id || null
  Object.keys(form).forEach((k) => delete form[k])
  Object.assign(form, {
    customer_id: presets.customer_id || null, contact_id: null, opportunity_id: presets.opportunity_id || null,
    method: '电话', time: '', content: '', next_time: '', next_content: '',
  })
  const p = id ? get(`/activities/${id}`) : Promise.resolve({})
  p.then((a) => {
    if (a && a.id) {
      Object.assign(form, {
        customer_id: a.customer_id, contact_id: a.contact_id, opportunity_id: a.opportunity_id,
        method: a.method || '电话', time: fmtDate(a.activity_time) || '', content: a.content || '',
        next_time: fmtDate(a.next_followup_time) || '', next_content: a.next_followup_content || '',
      })
    }
  })
  formVisible.value = true
}
async function saveForm() {
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
}
async function deleteActivity(id) {
  await ElMessageBox.confirm('确认删除该联络记录？', '删除记录')
  const r = await del(`/activities/${id}`)
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success('已删除'); load()
}

// ---- 详情 ----
const detailVisible = ref(false)
const detail = ref(null)
async function viewDetail(id) {
  detail.value = await get(`/activities/${id}`)
  detailVisible.value = true
}

async function doExport() {
  const err = await exportCsv('activities', filteredList.value)
  err ? ElMessage.error(err) : ElMessage.success(`已导出 ${filteredList.value.length} 条`)
}

onMounted(async () => {
  await Promise.all([load(), dict.loadCustomers(), dict.loadContacts(), dict.loadOpportunities()])
  if (window._presetActivity) {
    const p = window._presetActivity
    window._presetActivity = null
    openForm(null, p)
  }
})
</script>

<style scoped>
@media (max-width: 1000px) { .log-grid { grid-template-columns: 1fr !important; } }
</style>
