<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">商机管理</h2>
      <div class="page-toolbar">
        <el-radio-group v-model="view">
          <el-radio-button value="list">列表</el-radio-button>
          <el-radio-button value="board">看板</el-radio-button>
        </el-radio-group>
        <el-button :icon="Download" @click="doExport">导出</el-button>
        <el-button type="primary" :icon="Plus" @click="openForm()">新建商机</el-button>
      </div>
    </div>

    <FilterBar @search="applyFilter" @reset="resetFilter">
      <el-form-item label="名称">
        <el-input v-model="draft.q" placeholder="搜索商机名称..." clearable class="w-200" />
      </el-form-item>
      <el-form-item label="客户">
        <el-select v-model="draft.customer" clearable filterable class="w-180" @change="applyFilter">
          <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
        </el-select>
      </el-form-item>
      <el-form-item label="阶段">
        <el-select v-model="draft.stage" clearable class="w-140" @change="applyFilter">
          <el-option v-for="s in dict.stageNames" :key="s" :value="s" :label="s" />
        </el-select>
      </el-form-item>
    </FilterBar>

    <!-- 阶段分布：标准步骤条 -->
    <el-card shadow="never" class="card-block">
      <el-steps :active="stageData.length" align-center finish-status="success" class="stage-steps">
        <el-step v-for="s in stageData" :key="s.name" :title="s.name">
          <template #description>
            <div class="step-count">{{ s.items.length }} 个</div>
            <div class="step-amount">{{ sumAmount(s.items) }}万</div>
          </template>
        </el-step>
      </el-steps>
    </el-card>

    <!-- 列表视图 -->
    <el-card v-if="view === 'list'" shadow="never" body-class="p-0">
      <PageTable storage-key="opp" :data="filteredList" :loading="loading" :default-sort="{ prop: 'created_at', order: 'descending' }">
        <el-table-column prop="title" label="商机名称" min-width="200" sortable="custom" class-name="cell-strong" />
        <el-table-column prop="customer_name" label="客户" min-width="140" sortable="custom" show-overflow-tooltip />
        <el-table-column prop="amount" label="金额(万)" width="110" sortable="custom" align="right">
          <template #default="{ row }">{{ fmtNum(row.amount) }}</template>
        </el-table-column>
        <el-table-column prop="current_stage" label="阶段" width="110" sortable="custom">
          <template #default="{ row }">
            <el-tag size="small" effect="light">{{ row.current_stage || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="probability" label="赢率" width="90" sortable="custom" align="center">
          <template #default="{ row }">
            <span :style="{ color: probColor(row.probability || 20), fontWeight: 600 }">{{ row.probability || 20 }}%</span>
          </template>
        </el-table-column>
        <el-table-column prop="contact_name" label="联系人" width="110" />
        <el-table-column prop="expected_close" label="预计关闭" width="110" sortable="custom">
          <template #default="{ row }"><span class="muted">{{ fmtDate(row.expected_close) || '-' }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click.stop="viewDetail(row.id)">详情</el-button>
            <el-button link type="primary" size="small" @click.stop="openForm(row.id)">编辑</el-button>
            <el-button link type="danger" size="small" @click.stop="deleteOpp(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </PageTable>
    </el-card>

    <!-- 看板视图 -->
    <div v-else class="kanban-board">
      <div v-for="s in stageData" :key="s.name" class="kanban-col" :style="{ borderTopColor: s.color }">
        <div class="col-head">
          <span class="col-name">{{ s.name }}</span>
          <el-tag size="small" effect="light">{{ s.items.length }}</el-tag>
        </div>
        <div class="col-sum muted">合计 {{ sumAmount(s.items) }}万</div>
        <div v-for="o in s.items" :key="o.id" class="kanban-card" @click="viewDetail(o.id)">
          <div class="card-name">{{ o.title }}</div>
          <div class="muted card-cust">{{ o.customer_name || '-' }}</div>
          <div class="card-foot">
            <span class="card-amount">{{ fmtNum(o.amount) }}万</span>
            <span :style="{ color: probColor(o.probability || 20) }">{{ o.probability || 20 }}%</span>
          </div>
        </div>
        <el-empty v-if="!s.items.length" description="暂无商机" :image-size="48" />
      </div>
    </div>

    <!-- 新建 / 编辑商机 -->
    <el-dialog v-model="formVisible" :title="editId ? '编辑商机' : '新建商机'" width="600px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="110px">
        <el-form-item label="商机名称" prop="title">
          <el-input v-model="form.title" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="客户">
              <el-select v-model="form.customer_id" clearable filterable class="w-full">
                <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系人">
              <el-select v-model="form.contact_id" clearable filterable class="w-full">
                <el-option v-for="c in dict.contacts" :key="c.id" :value="c.id" :label="c.name" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="金额(万)">
              <el-input-number v-model="form.amount" :min="0" :precision="2" controls-position="right" class="w-full" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="赢率(%)">
              <el-input-number v-model="form.probability" :min="0" :max="100" :step="5" controls-position="right" class="w-full" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="阶段" prop="current_stage">
              <el-select v-model="form.current_stage" class="w-full">
                <el-option v-for="s in dict.stageNames" :key="s" :value="s" :label="s" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="预计关闭">
              <el-date-picker v-model="form.expected_close" type="date" value-format="YYYY-MM-DD" class="w-full" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="来源URL">
          <el-input v-model="form.source_url" placeholder="https://..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingForm" @click="saveForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 商机详情 -->
    <el-dialog v-model="detailVisible" :title="detail?.title || '商机详情'" width="720px" destroy-on-close>
      <div v-loading="detailLoading" class="detail-body">
        <template v-if="detail">
          <DetailGrid :items="[
            { label: '客户', value: detail.customer_name },
            { label: '联系人', value: detail.contact_name },
            { label: '金额', value: `${fmtNum(detail.amount)}万` },
            { label: '预计关闭', value: fmtDate(detail.expected_close) || '-' },
            { label: '阶段', slot: 'stage' },
            { label: '赢率', slot: 'prob' },
            { label: '来源', slot: 'src' },
          ]">
            <template #stage>
              <el-tag size="small" effect="light">{{ detail.current_stage || '-' }}</el-tag>
            </template>
            <template #prob>
              <span :style="{ color: probColor(detail.probability || 20), fontWeight: 600 }">{{ detail.probability || 20 }}%</span>
            </template>
            <template #src>
              <el-link v-if="detail.source_url" type="primary" :href="detail.source_url" target="_blank">查看招标原文</el-link>
              <span v-else class="muted">手工添加</span>
            </template>
          </DetailGrid>

          <el-space class="detail-actions">
            <el-button type="primary" size="small" :icon="Plus" @click="addActivity">添加联络记录</el-button>
            <el-button size="small" :icon="Edit" @click="openForm(detail.id)">编辑商机</el-button>
          </el-space>

          <el-divider content-position="left">流转时间轴（日常联络记录）</el-divider>
          <el-timeline v-if="acts.length">
            <el-timeline-item v-for="a in acts" :key="a.id" :timestamp="`${fmtDate(a.activity_time) || ''} ${a.method || ''}`">
              {{ a.content }}
              <span v-if="a.contact_name" class="muted">（联系人: {{ a.contact_name }}）</span>
              <div v-if="a.next_followup_time" class="next-followup">
                预计下次: {{ fmtDate(a.next_followup_time) }} {{ a.next_followup_content || '' }}
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无联络记录" :image-size="60" />

          <template v-if="(detail.stages || []).length">
            <el-divider content-position="left">阶段记录</el-divider>
            <el-timeline>
              <el-timeline-item v-for="(s, i) in detail.stages" :key="i" :timestamp="fmtDate(s.created_at)">
                {{ s.stage }}: {{ s.content || '' }}
              </el-timeline-item>
            </el-timeline>
          </template>
        </template>
      </div>
      <template #footer><el-button @click="detailVisible = false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Download, Edit } from '@element-plus/icons-vue'
import PageTable from '../components/PageTable.vue'
import FilterBar from '../components/FilterBar.vue'
import DetailGrid from '../components/DetailGrid.vue'
import { get, getList, post, put, del, fmtDate, fmtNum, exportCsv, probColor, stageColor } from '../api'
import { useDictStore } from '../stores/app'

const route = useRoute()
const router = useRouter()
const dict = useDictStore()
const opps = ref([])
const loading = ref(false)
const view = ref('list')
const filter = reactive({ q: '', customer: '', stage: '' })
const draft = reactive({ q: '', customer: '', stage: '' })

const filteredList = computed(() => opps.value.filter((o) => {
  if (filter.q && !(o.title || '').toLowerCase().includes(filter.q.toLowerCase())) return false
  if (filter.customer && String(o.customer_id) !== String(filter.customer)) return false
  if (filter.stage && o.current_stage !== filter.stage) return false
  return true
}))

const stageData = computed(() => dict.stageNames.map((s) => ({
  name: s,
  color: stageColor(s, dict.stageNames),
  items: filteredList.value.filter((o) => o.current_stage === s),
})))

const sumAmount = (items) => fmtNum(items.reduce((a, o) => a + parseFloat(o.amount || 0), 0))

async function load() {
  loading.value = true
  opps.value = await getList('/opportunities')
  loading.value = false
}
function applyFilter() { Object.assign(filter, draft) }
function resetFilter() {
  Object.assign(draft, { q: '', customer: '', stage: '' })
  Object.assign(filter, draft)
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
  detailVisible.value = true
  detailLoading.value = true
  detail.value = await get(`/opportunities/${id}`)
  detailLoading.value = false
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
.w-full { width: 100%; }
.w-200 { width: 200px; }
.w-180 { width: 180px; }
.w-140 { width: 140px; }

/* 阶段步骤条 */
.stage-steps { padding: 4px 0; }
.stage-steps :deep(.el-step__title) { font-size: 13px; }
.step-count { font-size: 16px; font-weight: 600; color: var(--el-text-color-primary); line-height: 1.4; }
.step-amount { font-size: 12px; color: var(--el-text-color-secondary); }

/* 看板视图 */
.kanban-board { display: flex; gap: 12px; overflow-x: auto; padding-bottom: 4px; align-items: flex-start; }
.kanban-col {
  background: var(--el-fill-color-light);
  border-top: 3px solid var(--el-color-primary);
  border-radius: var(--el-border-radius-base);
  width: 260px; flex: 0 0 260px; padding: 10px;
}
.col-head { display: flex; align-items: center; justify-content: space-between; padding: 2px 4px 6px; }
.col-name { font-weight: 600; font-size: 13px; color: var(--el-text-color-primary); }
.col-sum { padding: 0 4px 8px; }
.kanban-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: var(--el-border-radius-base);
  padding: 10px 12px; margin-bottom: 8px; cursor: pointer;
  transition: box-shadow .15s;
}
.kanban-card:hover { box-shadow: var(--el-box-shadow-light); }
.card-name { font-weight: 500; font-size: 13px; margin-bottom: 4px; }
.card-cust { margin-bottom: 6px; }
.card-foot { display: flex; justify-content: space-between; font-size: 12px; }
.card-amount { font-weight: 600; }

/* 详情 */
.detail-body { min-height: 80px; }
.detail-actions { margin: 16px 0; }
.next-followup { color: var(--el-color-warning); font-size: 12px; }
</style>
