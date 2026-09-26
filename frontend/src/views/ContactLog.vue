<template>
  <div class="page">
    <PageHeader title="日常联络" subtitle="客户触达的完整流水：每一次电话、拜访、微信都留痕">
      <template #actions>
        <el-button :icon="Download" plain @click="doExport">导出</el-button>
        <el-button type="primary" :icon="Plus" @click="openForm()">新增联络</el-button>
      </template>
    </PageHeader>

    <FilterBar @search="applyFilter" @reset="resetFilter">
      <el-form-item label="开始日期">
        <el-date-picker v-model="draft.date_from" type="date" value-format="YYYY-MM-DD" placeholder="起始" style="width:150px" />
      </el-form-item>
      <el-form-item label="结束日期">
        <el-date-picker v-model="draft.date_to" type="date" value-format="YYYY-MM-DD" placeholder="结束" style="width:150px" />
      </el-form-item>
      <el-form-item label="客户">
        <el-select v-model="draft.customer" clearable filterable placeholder="全部客户" style="width:180px" @change="applyFilter">
          <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
        </el-select>
      </el-form-item>
      <el-form-item label="商机">
        <el-select v-model="draft.opp" clearable filterable placeholder="全部商机" style="width:190px" @change="applyFilter">
          <el-option v-for="o in dict.opportunities" :key="o.id" :value="o.id" :label="o.title" />
        </el-select>
      </el-form-item>
      <el-form-item label="内容">
        <el-input v-model="draft.q" placeholder="搜索内容..." clearable style="width:180px" />
      </el-form-item>
    </FilterBar>

    <div class="table-wrap">
      <PageTable
          storage-key="activity" :data="filteredList" :loading="loading"
          :default-sort="{ prop: 'activity_time', order: 'descending' }"
          empty-text="暂无联络记录" empty-hint="记录每一次沟通，商机页的时间轴会自动同步"
        >
          <template #empty-action>
            <el-button type="primary" plain size="small" :icon="Plus" @click="openForm()" style="margin-top:12px">新增联络</el-button>
          </template>

          <el-table-column prop="id" label="编号" width="86" sortable="custom">
            <template #default="{ row }">
              <span class="mono serial">{{ actNo(row.id) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="activity_time" label="时间" width="112" sortable="custom">
            <template #default="{ row }">
              <span class="mono date">{{ fmtDateMDY(row.activity_time) || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="method" label="方式" width="88" sortable="false">
            <template #default="{ row }">
              <span v-if="row.method" class="method-chip">{{ row.method }}</span>
              <span v-else class="dim">—</span>
            </template>
          </el-table-column>
          <el-table-column prop="customer_name" label="客户 / 联系人" min-width="170" sortable="custom">
            <template #default="{ row }">
              <div class="cell-title-text" :title="row.customer_name">{{ row.customer_name || '—' }}</div>
              <div v-if="row.contact_name" class="cell-meta">{{ row.contact_name }}</div>
            </template>
          </el-table-column>
          <el-table-column prop="opportunity_title" label="商机" min-width="140" sortable="custom" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.opportunity_title" class="opp-chip">{{ row.opportunity_title }}</span>
              <span v-else class="dim">—</span>
            </template>
          </el-table-column>
          <el-table-column prop="content" label="内容" min-width="240" sortable="custom">
            <template #default="{ row }">
              <div class="content-cell" :title="row.content">{{ row.content || '—' }}</div>
            </template>
          </el-table-column>
          <el-table-column prop="next_followup_time" label="预计联系" width="112" sortable="custom">
            <template #default="{ row }">
              <span v-if="row.next_followup_time" class="mono date is-next">{{ fmtDateMDY(row.next_followup_time) }}</span>
              <span v-else class="mono dim">—</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right" align="right">
            <template #default="{ row }">
              <div class="row-actions">
                <el-button link type="primary" size="small" @click="viewDetail(row.id)">查看</el-button>
                <el-button link size="small" @click="openForm(row.id)">编辑</el-button>
                <el-button link type="danger" size="small" @click="deleteActivity(row.id)">删除</el-button>
              </div>
            </template>
          </el-table-column>
        </PageTable>
    </div>

    <!-- 新增 / 编辑联络 -->
    <el-dialog v-model="formVisible" :title="editId ? '编辑联络记录' : '新增日常联络'" width="700px" destroy-on-close class="form-dialog">
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="108px" label-position="right">
        <div class="form-section">
          <div class="section-title">联络对象</div>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="客户" prop="customer_id">
                <el-select v-model="form.customer_id" clearable filterable placeholder="从客户库选择" style="width:100%" @change="form.contact_id = null">
                  <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="联系人">
                <el-select v-model="form.contact_id" clearable filterable placeholder="先选客户再选联系人" style="width:100%">
                  <el-option v-for="c in dict.contactsOf(form.customer_id)" :key="c.id" :value="c.id" :label="c.name" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="关联商机">
            <el-select v-model="form.opportunity_id" clearable filterable placeholder="选填" style="width:100%">
              <el-option v-for="o in dict.opportunities" :key="o.id" :value="o.id" :label="o.title" />
            </el-select>
            <div class="field-hint">非必选；可只联系客户增进感情，或挂到具体商机</div>
          </el-form-item>
        </div>

        <div class="form-section">
          <div class="section-title">本次沟通</div>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="方式" prop="method">
                <el-select v-model="form.method" style="width:100%">
                  <el-option v-for="m in METHOD_OPTIONS" :key="m" :value="m" :label="m" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="时间" prop="time">
                <el-date-picker v-model="form.time" type="date" value-format="YYYY-MM-DD" style="width:100%" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="内容" prop="content">
            <el-input v-model="form.content" type="textarea" :rows="3" placeholder="沟通要点、客户反馈、下一步承诺…" />
          </el-form-item>
        </div>

        <div class="form-section">
          <div class="section-title">下次跟进</div>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="下次日期">
                <el-date-picker v-model="form.next_time" type="date" value-format="YYYY-MM-DD" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="下次内容">
                <el-input v-model="form.next_content" placeholder="如：寄送样材料" />
              </el-form-item>
            </el-col>
          </el-row>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingForm" @click="saveForm">{{ editId ? '保存修改' : '记录联络' }}</el-button>
      </template>
    </el-dialog>

    <!-- 详情 -->
    <el-dialog v-model="detailVisible" title="联络记录详情" width="680px" destroy-on-close class="detail-dialog">
      <div v-loading="detailLoading" class="detail-loading-wrap">
        <template v-if="detail">
          <div class="detail-hero">
            <div class="detail-hero-body">
              <div class="detail-hero-title">{{ detail.customer_name || '未关联客户' }}</div>
              <div class="detail-hero-meta">
                <span class="mono hero-serial">{{ actNo(detail.id) }}</span>
                <span class="mono hero-date">{{ fmtDate(detail.activity_time) || '—' }}</span>
                <span v-if="detail.method" class="method-chip">{{ detail.method }}</span>
                <span v-if="detail.contact_name" class="hero-chip">{{ detail.contact_name }}</span>
              </div>
            </div>
          </div>
          <div class="detail-body">
            <DetailGrid :items="[
              { label: '关联商机', value: detail.opportunity_title || '' },
              { label: '预计联系', value: fmtDate(detail.next_followup_time) || '', mono: true },
            ]" dense />

            <div class="section-title">联络内容</div>
            <div class="content-block">{{ detail.content || '—' }}</div>

            <template v-if="detail.next_followup_content">
              <div class="section-title">预计联系内容</div>
              <div class="content-block content-block--next">{{ detail.next_followup_content }}</div>
            </template>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button v-if="detail" @click="openForm(detail.id)">编辑</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Download } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'
import PageTable from '../components/PageTable.vue'
import FilterBar from '../components/FilterBar.vue'
import DetailGrid from '../components/DetailGrid.vue'
import { get, getList, post, put, del, fmtDate, fmtDateMDY, exportCsv, METHOD_OPTIONS } from '../api'
import { useDictStore } from '../stores/app'

const route = useRoute()
const dict = useDictStore()
const activities = ref([])
const loading = ref(false)
const actNo = (id) => (id === null || id === undefined ? '—' : String(id).padStart(6, '0'))
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
  const list = await getList('/activities')
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
  const r = await get(`/activities/${id}`)
  if (!r || r.error) return ElMessage.error('加载联络详情失败：' + ((r && r.error) || '请稍后重试'))
  detail.value = r
  detailVisible.value = true
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
/* ---- 布局 ---- */
.table-wrap {
  background: var(--crm-bg-card);
  border: 1px solid var(--crm-border-soft);
  border-radius: var(--crm-radius-lg);
  overflow: hidden;
  box-shadow: var(--crm-shadow-xs);
}

/* ---- 单元格 ---- */
.serial { font-size: 12px; color: var(--crm-fg-3); letter-spacing: 0.01em; }
.hero-serial {
  padding: 1px 8px; border-radius: var(--crm-radius-sm);
  background: var(--crm-slate-100); color: var(--crm-fg-2); font-size: 12px;
}
.cell-title-text {
  color: var(--crm-fg-1); font-weight: 500; font-size: 13.5px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.cell-meta { font-size: 11.5px; color: var(--crm-fg-3); margin-top: 2px; }
.date { font-size: 12px; }
.date.is-next { color: var(--crm-amber-500); font-weight: 500; }
.method-chip {
  display: inline-block; padding: 1px 8px;
  font-size: 11.5px; border-radius: var(--crm-radius-full);
  background: var(--crm-pine-25); color: var(--crm-pine-600); font-weight: 500;
}
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
.row-actions { display: inline-flex; gap: 0; justify-content: flex-end; align-items: center; }
.row-actions :deep(.el-button.is-link) { padding: 2px 6px; }

/* ---- 表单 ---- */
.form-section { margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px dashed var(--crm-border-soft); }
.form-section:last-child { margin-bottom: 0; padding-bottom: 0; border-bottom: none; }
.field-hint { font-size: 11.5px; color: var(--crm-fg-4); margin-top: 2px; line-height: 1.5; }

/* ---- 详情弹窗 ---- */
.detail-dialog :deep(.el-dialog__body) { padding: 0 !important; }
.detail-loading-wrap { min-height: 100px; }
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
.detail-hero-meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 12px; color: var(--crm-fg-3); }
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
.content-block--next { background: var(--crm-amber-50); border-color: #f5dfb8; }

@media (max-width: 768px) {
  .detail-hero { padding: 16px 18px; }
  .detail-body { padding: 16px 18px 0; }
}
</style>
