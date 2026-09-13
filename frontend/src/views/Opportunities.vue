<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">商机管理</h2>
      <div class="page-toolbar">
        <el-radio-group v-model="view" size="default">
          <el-radio-button value="list">列表</el-radio-button>
          <el-radio-button value="board">看板</el-radio-button>
        </el-radio-group>
        <el-button @click="doExport"><el-icon><Download /></el-icon>&nbsp;导出</el-button>
        <el-button type="primary" @click="openForm()"><el-icon><Plus /></el-icon>&nbsp;新建商机</el-button>
      </div>
    </div>

    <FilterBar @search="applyFilter" @reset="resetFilter">
      <el-form-item label="名称">
        <el-input v-model="draft.q" placeholder="搜索商机名称..." clearable style="width:200px" />
      </el-form-item>
      <el-form-item label="客户">
        <el-select v-model="draft.customer" clearable filterable style="width:180px" @change="applyFilter">
          <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
        </el-select>
      </el-form-item>
      <el-form-item label="阶段">
        <el-select v-model="draft.stage" clearable style="width:140px" @change="applyFilter">
          <el-option v-for="s in dict.stageNames" :key="s" :value="s" :label="s" />
        </el-select>
      </el-form-item>
    </FilterBar>

    <!-- 阶段 pipeline -->
    <el-card shadow="never" class="card-block" body-style="padding:14px 20px">
      <div class="pipeline">
        <template v-for="(s, i) in stageData" :key="s.name">
          <div class="pipeline-step">
            <div class="pipeline-dot" :style="{ background: s.color }">{{ s.items.length }}</div>
            <div class="pipeline-meta">
              <div class="pipeline-name" :style="{ color: s.color, fontWeight: 600 }">{{ s.name }}</div>
              <div class="pipeline-amt">{{ s.items.reduce((a, o) => a + parseFloat(o.amount || 0), 0) }}万</div>
            </div>
          </div>
          <div v-if="i < stageData.length - 1" class="pipeline-line"></div>
        </template>
      </div>
    </el-card>

    <!-- 列表视图 -->
    <el-card v-if="view === 'list'" shadow="never" body-style="padding:0">
      <PageTable storage-key="opp" :data="filteredList" :loading="loading" :default-sort="{ prop: 'created_at', order: 'descending' }">
        <el-table-column prop="title" label="商机名称" min-width="220" sortable="custom">
          <template #default="{ row }"><span style="font-weight:500">{{ row.title }}</span></template>
        </el-table-column>
        <el-table-column prop="customer_name" label="客户" min-width="150" sortable="custom" show-overflow-tooltip />
        <el-table-column prop="amount" label="金额" width="110" sortable="custom" align="right">
          <template #default="{ row }"><strong>{{ row.amount || 0 }}万</strong></template>
        </el-table-column>
        <el-table-column prop="current_stage" label="阶段" width="110" sortable="custom">
          <template #default="{ row }">
            <el-tag size="small" :color="stageColor(row.current_stage, dict.stageNames)" effect="dark" style="border:none">
              {{ row.current_stage }}
            </el-tag>
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
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click.stop="viewDetail(row.id)">详情</el-button>
            <el-button link type="primary" size="small" @click.stop="openForm(row.id)">编辑</el-button>
            <el-button link type="danger" size="small" @click.stop="deleteOpp(row.id)"><el-icon><Delete /></el-icon></el-button>
          </template>
        </el-table-column>
      </PageTable>
    </el-card>

    <!-- 看板视图 -->
    <div v-else class="kanban-board">
      <div v-for="s in stageData" :key="s.name" class="kanban-col" :style="{ borderTop: `3px solid ${s.color}` }">
        <div style="display:flex;align-items:center;justify-content:space-between;padding:2px 4px 8px">
          <span style="font-weight:600;font-size:13px">{{ s.name }}</span>
          <el-tag size="small" :color="s.color" effect="dark" style="border:none">{{ s.items.length }}</el-tag>
        </div>
        <div class="muted" style="margin-bottom:8px;padding:0 4px">合计: {{ s.items.reduce((a, o) => a + parseFloat(o.amount || 0), 0) }}万</div>
        <div v-for="o in s.items" :key="o.id" class="kanban-card" style="cursor:pointer" @click="viewDetail(o.id)">
          <div style="font-weight:500;font-size:12px;margin-bottom:4px">{{ o.title }}</div>
          <div class="muted" style="margin-bottom:6px">{{ o.customer_name }}</div>
          <div style="display:flex;justify-content:space-between;font-size:12px">
            <span style="font-weight:600">{{ o.amount || 0 }}万</span>
            <span :style="{ color: probColor(o.probability || 20) }">{{ o.probability || 20 }}%</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 新建/编辑商机 -->
    <el-dialog v-model="formVisible" :title="editId ? '编辑商机' : '新建商机'" width="600px" destroy-on-close>
      <el-form :model="form" label-width="110px">
        <el-form-item label="商机名称" required><el-input v-model="form.title" /></el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="客户">
              <el-select v-model="form.customer_id" clearable filterable style="width:100%">
                <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系人">
              <el-select v-model="form.contact_id" clearable filterable style="width:100%">
                <el-option v-for="c in dict.contacts" :key="c.id" :value="c.id" :label="c.name" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12"><el-form-item label="金额(万)"><el-input v-model="form.amount" type="number" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="赢率(%)"><el-input v-model="form.probability" type="number" :min="0" :max="100" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="阶段">
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
        <el-form-item label="来源URL"><el-input v-model="form.source_url" placeholder="https://..." /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" @click="saveForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 商机详情 -->
    <el-dialog v-model="detailVisible" :title="detail?.title || '商机详情'" width="720px" destroy-on-close>
      <template v-if="detail">
        <DetailGrid :items="[
          { label: '客户', value: detail.customer_name },
          { label: '联系人', value: detail.contact_name },
          { label: '金额', value: `${detail.amount || 0}万` },
          { label: '阶段', value: `${detail.current_stage || '-'} | 赢率 ${detail.probability || 20}%` },
          { label: '预计关闭', value: fmtDate(detail.expected_close) || '-' },
          { label: '来源', slot: 'src' },
        ]" style="margin-bottom:14px">
          <template #src>
            <a v-if="detail.source_url" :href="detail.source_url" target="_blank" style="color:var(--el-color-primary)">查看招标原文</a>
            <span v-else>手工添加</span>
          </template>
        </DetailGrid>
        <div style="display:flex;gap:8px;margin-bottom:14px">
          <el-button type="primary" size="small" @click="addActivity">
            <el-icon><Plus /></el-icon>&nbsp;添加联络记录
          </el-button>
          <el-button size="small" @click="openForm(detail.id)">
            <el-icon><Edit /></el-icon>&nbsp;编辑商机
          </el-button>
        </div>
        <div style="font-weight:600;font-size:13px;margin-bottom:8px">流转时间轴（日常联络记录）</div>
        <el-timeline v-if="acts.length" style="padding-left:4px">
          <el-timeline-item v-for="a in acts" :key="a.id" :timestamp="`${fmtDate(a.activity_time) || ''} ${a.method || ''}`">
            {{ a.content }}
            <span v-if="a.contact_name" class="muted">（联系人: {{ a.contact_name }}）</span>
            <div v-if="a.next_followup_time" style="color:var(--el-color-warning);font-size:12px">
              预计下次: {{ fmtDate(a.next_followup_time) }} {{ a.next_followup_content || '' }}
            </div>
          </el-timeline-item>
        </el-timeline>
        <div v-else class="muted">暂无联络记录</div>
        <template v-if="(detail.stages || []).length">
          <div style="font-weight:600;font-size:13px;margin:14px 0 8px">阶段记录</div>
          <el-timeline style="padding-left:4px">
            <el-timeline-item v-for="(s, i) in detail.stages" :key="i" :timestamp="fmtDate(s.created_at)">
              {{ s.stage }}: {{ s.content || '' }}
            </el-timeline-item>
          </el-timeline>
        </template>
      </template>
      <template #footer><el-button @click="detailVisible = false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Download, Delete, Edit } from '@element-plus/icons-vue'
import PageTable from '../components/PageTable.vue'
import FilterBar from '../components/FilterBar.vue'
import DetailGrid from '../components/DetailGrid.vue'
import { get, post, put, del, fmtDate, exportCsv, probColor, stageColor } from '../api'
import { useDictStore } from '../stores/app'

const dict = useDictStore()
const opps = ref([])
const loading = ref(false)
const view = ref('list')
const filter = reactive({ q: '', customer: '', stage: '' })
const draft = reactive({ q: '', customer: '', stage: '' })

const filteredList = computed(() => opps.value.filter((o) => {
  if (filter.q && !o.title.toLowerCase().includes(filter.q.toLowerCase())) return false
  if (filter.customer && String(o.customer_id) !== String(filter.customer)) return false
  if (filter.stage && o.current_stage !== filter.stage) return false
  return true
}))
const stageData = computed(() => dict.stageNames.map((s, i) => ({
  name: s,
  color: stageColor(s, dict.stageNames) || ['#94a3b8', '#3b82f6', '#f59e0b', '#8b5cf6', '#166534'][i % 5],
  items: filteredList.value.filter((o) => o.current_stage === s),
})))

async function load() {
  loading.value = true
  opps.value = (await get('/opportunities')) || []
  loading.value = false
}
function applyFilter() { Object.assign(filter, draft) }
function resetFilter() {
  Object.assign(draft, { q: '', customer: '', stage: '' })
  Object.assign(filter, draft)
}

// ---- 新建/编辑 ----
const formVisible = ref(false)
const editId = ref(null)
const form = reactive({})
function openForm(id) {
  editId.value = id || null
  Object.keys(form).forEach((k) => delete form[k])
  Object.assign(form, { title: '', customer_id: null, contact_id: null, amount: '', probability: 20, current_stage: dict.stageNames[0] || '', expected_close: '', source_url: '' })
  if (id) get(`/opportunities/${id}`).then((o) => { Object.keys(form).forEach((k) => (form[k] = o[k] ?? form[k])) })
  formVisible.value = true
}
async function saveForm() {
  if (!form.title) return ElMessage.error('请输入名称')
  const d = { ...form, probability: parseInt(form.probability) || 20 }
  const r = editId.value ? await put(`/opportunities/${editId.value}`, d) : await post('/opportunities', d)
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success(editId.value ? '更新成功' : '创建成功')
  formVisible.value = false
  load(); dict.loadOpportunities()
}
async function deleteOpp(id) {
  await ElMessageBox.confirm('确认删除该商机？', '删除商机')
  const r = await del(`/opportunities/${id}`)
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success('已删除'); load()
}

// ---- 详情 ----
const detailVisible = ref(false)
const detail = ref(null)
const acts = computed(() => (detail.value?.activities || []).slice().reverse())
async function viewDetail(id) {
  detail.value = await get(`/opportunities/${id}`)
  detailVisible.value = true
}
function addActivity() {
  detailVisible.value = false
  window._presetActivity = { opportunity_id: detail.value.id, customer_id: detail.value.customer_id }
  window.location.hash = '#/contactlog'
}
// 从客户详情跳来直接打开商机
onMounted(async () => {
  await Promise.all([load(), dict.loadCustomers(), dict.loadContacts(), dict.loadStages()])
  if (window._presetOppDetail) {
    const id = window._presetOppDetail
    window._presetOppDetail = null
    viewDetail(id)
  }
})
async function doExport() {
  const err = await exportCsv('opportunities', filteredList.value)
  err ? ElMessage.error(err) : ElMessage.success(`已导出 ${filteredList.value.length} 条`)
}
</script>
