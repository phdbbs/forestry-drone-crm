<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">客户管理</h2>
      <div class="page-toolbar">
        <el-button :icon="Download" @click="doExport">导出</el-button>
        <el-button type="primary" :icon="Plus" @click="openForm()">新增客户</el-button>
      </div>
    </div>

    <FilterBar @search="applyFilter" @reset="resetFilter">
      <el-form-item label="名称">
        <el-input v-model="draft.q" placeholder="搜索客户名称..." clearable class="w-200" />
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="draft.type" clearable class="w-140" @change="applyFilter">
          <el-option v-for="t in typeOptions" :key="t" :value="t" :label="t" />
        </el-select>
      </el-form-item>
      <el-form-item label="等级">
        <el-select v-model="draft.level" clearable class="w-140" @change="applyFilter">
          <el-option v-for="l in levelOptions" :key="l" :value="l" :label="l" />
        </el-select>
      </el-form-item>
      <el-form-item label="地区">
        <el-input v-model="draft.region" placeholder="如: 浙江" clearable class="w-140" />
      </el-form-item>
    </FilterBar>

    <el-card shadow="never" body-class="p-0">
      <PageTable storage-key="customer" :data="filteredList" :loading="loading" :default-sort="{ prop: 'name', order: 'ascending' }">
        <el-table-column prop="name" label="客户名称" min-width="220" sortable="custom" class-name="cell-strong" />
        <el-table-column prop="type" label="类型" width="120" sortable="custom" />
        <el-table-column prop="level" label="等级" width="130" sortable="custom">
          <template #default="{ row }">
            <el-tag v-if="row.level" size="small" effect="light" :type="levelTagType(row.level)">{{ row.level }}</el-tag>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="region" label="地区" width="120" sortable="custom" />
        <el-table-column prop="contact_count" label="联系人" width="100" sortable="custom" align="center">
          <template #default="{ row }">{{ row.contact_count || 0 }} 人</template>
        </el-table-column>
        <el-table-column prop="source" label="来源" min-width="130" show-overflow-tooltip />
        <el-table-column label="操作" width="150" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewDetail(row.id)">查看</el-button>
            <el-button link type="primary" size="small" @click="openForm(row.id)">编辑</el-button>
            <el-button link type="danger" size="small" @click="deleteCustomer(row.id)">归档</el-button>
          </template>
        </el-table-column>
      </PageTable>
    </el-card>

    <!-- 新增 / 编辑客户 -->
    <el-dialog v-model="formVisible" :title="editId ? '编辑客户' : '新增客户'" width="560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="150px">
        <el-form-item label="客户名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="官网" prop="website">
          <el-input v-model="form.website" placeholder="https://...（用于新闻采集）" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="类型">
              <el-select v-model="form.type" clearable class="w-full">
                <el-option v-for="t in dict.options.customer_types" :key="t" :value="t" :label="t" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="等级">
              <el-select v-model="form.level" clearable class="w-full">
                <el-option v-for="l in dict.options.customer_levels" :key="l" :value="l" :label="l" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="地区">
              <el-select v-model="form.region" clearable filterable class="w-full">
                <el-option v-for="r in dict.options.regions" :key="r" :value="r" :label="r" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="来源">
              <el-input v-model="form.source" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingForm" @click="saveForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 客户详情（4 tab） -->
    <el-dialog v-model="detailVisible" :title="detail?.name || '客户详情'" width="760px" destroy-on-close>
      <div v-loading="detailLoading" class="detail-body">
        <template v-if="detail">
          <DetailGrid :items="[
            { label: '类型', value: detail.type },
            { label: '等级', value: detail.level },
            { label: '地区', value: detail.region },
            { label: '来源', value: detail.source },
          ]" />

          <el-tabs v-model="custTab" class="detail-tabs">
            <!-- 联系人 -->
            <el-tab-pane :label="`联系人 (${(detail.contacts || []).length})`" name="contacts">
              <el-table v-if="(detail.contacts || []).length" :data="detail.contacts" size="small">
                <el-table-column prop="name" label="姓名" width="110" />
                <el-table-column prop="title" label="职务" min-width="130" show-overflow-tooltip />
                <el-table-column prop="phone" label="电话" width="150" />
                <el-table-column label="重要度" width="90">
                  <template #default="{ row }">
                    <el-tag v-if="row.importance" size="small" type="warning" effect="light">{{ row.importance }}</el-tag>
                    <span v-else class="muted">-</span>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-else description="暂无联系人" :image-size="60" />
            </el-tab-pane>

            <!-- 商机 -->
            <el-tab-pane :label="`商机 (${(detail.opportunities || []).length})`" name="opps">
              <template v-if="(detail.opportunities || []).length">
                <el-table :data="detail.opportunities" size="small">
                  <el-table-column label="商机名称" min-width="220">
                    <template #default="{ row }">
                      <el-link type="primary" @click="openOppFromCustomer(row.id)">{{ row.title }}</el-link>
                    </template>
                  </el-table-column>
                  <el-table-column label="金额(万)" width="100" align="right">
                    <template #default="{ row }">{{ fmtNum(row.amount) }}</template>
                  </el-table-column>
                  <el-table-column label="阶段" width="110">
                    <template #default="{ row }">{{ row.current_stage || '-' }}</template>
                  </el-table-column>
                  <el-table-column label="赢率" width="80" align="center">
                    <template #default="{ row }">{{ row.probability || 20 }}%</template>
                  </el-table-column>
                </el-table>
                <div class="muted hint">点击商机名称跳转到商机管理查看详情</div>
              </template>
              <el-empty v-else description="该客户暂无商机" :image-size="60" />
            </el-tab-pane>

            <!-- 联络记录 -->
            <el-tab-pane label="联络记录" name="acts">
              <el-space class="tab-actions">
                <el-button type="primary" size="small" :icon="Plus" @click="addActivityFromCustomer">新增日常联络</el-button>
              </el-space>
              <el-table :data="custActs" size="small" v-loading="actsLoading">
                <el-table-column label="时间" width="110">
                  <template #default="{ row }">{{ fmtDate(row.activity_time) || '-' }}</template>
                </el-table-column>
                <el-table-column label="联系人" width="100">
                  <template #default="{ row }">{{ row.contact_name || '-' }}</template>
                </el-table-column>
                <el-table-column label="内容" min-width="240" show-overflow-tooltip>
                  <template #default="{ row }">{{ row.content || '-' }}</template>
                </el-table-column>
                <el-table-column label="预计联系" width="110">
                  <template #default="{ row }">{{ fmtDate(row.next_followup_time) || '-' }}</template>
                </el-table-column>
              </el-table>
              <el-empty v-if="!custActs.length && !actsLoading" description="暂无联络记录" :image-size="60" />
            </el-tab-pane>

            <!-- 动态信息 -->
            <el-tab-pane :label="`动态信息 (${(detail.news || []).length})`" name="news">
              <el-space class="tab-actions">
                <el-button type="primary" size="small" :icon="Lightning" :loading="newsLoading" @click="collectNews">采集新闻</el-button>
              </el-space>
              <el-table v-if="(detail.news || []).length" :data="detail.news" size="small">
                <el-table-column label="采集时间" width="110">
                  <template #default="{ row }">{{ fmtDate(row.date) || '-' }}</template>
                </el-table-column>
                <el-table-column label="来源" width="140">
                  <template #default="{ row }">{{ row.source_name || '-' }}</template>
                </el-table-column>
                <el-table-column label="新闻标题" min-width="240">
                  <template #default="{ row }">
                    {{ row.title }}
                    <div v-if="row.content" class="muted">{{ row.content.slice(0, 80) }}</div>
                  </template>
                </el-table-column>
                <el-table-column label="事件时间" width="110">
                  <template #default="{ row }">{{ row.event_time || '-' }}</template>
                </el-table-column>
                <el-table-column label="操作" width="70" align="center">
                  <template #default="{ row }">
                    <el-button link type="danger" size="small" @click="deleteNews(row.id)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-else description="暂无动态信息，点击采集" :image-size="60" />
            </el-tab-pane>
          </el-tabs>
        </template>
      </div>
      <template #footer><el-button @click="detailVisible = false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Download, Lightning } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import PageTable from '../components/PageTable.vue'
import FilterBar from '../components/FilterBar.vue'
import DetailGrid from '../components/DetailGrid.vue'
import { get, getList, post, put, del, fmtDate, fmtNum, exportCsv } from '../api'
import { useDictStore } from '../stores/app'

const dict = useDictStore()
const router = useRouter()
const TYPE_OPTIONS = ['政府部门', '事业单位', '国有企业', '民营企业', '科研院所', '运营商', '科技公司']
const LEVEL_OPTIONS = ['A-重点客户', 'B-重要客户', 'C-一般客户', 'D-潜在客户']
const typeOptions = computed(() => (dict.options.customer_types?.length ? dict.options.customer_types : TYPE_OPTIONS))
const levelOptions = computed(() => (dict.options.customer_levels?.length ? dict.options.customer_levels : LEVEL_OPTIONS))

const levelTagType = (lv) => (lv.includes('A') ? 'danger' : lv.includes('B') ? 'warning' : 'info')

const customers = ref([])
const loading = ref(false)
const filter = reactive({ q: '', type: '', level: '', region: '' })
const draft = reactive({ q: '', type: '', level: '', region: '' })

const filteredList = computed(() => customers.value.filter((cu) => {
  if (filter.q && !(cu.name || '').toLowerCase().includes(filter.q.toLowerCase())) return false
  if (filter.type && cu.type !== filter.type) return false
  if (filter.level && cu.level !== filter.level) return false
  if (filter.region && !(cu.region || '').includes(filter.region)) return false
  return true
}))

async function load() {
  loading.value = true
  customers.value = await getList('/customers')
  loading.value = false
}
function applyFilter() { Object.assign(filter, draft) }
function resetFilter() {
  Object.assign(draft, { q: '', type: '', level: '', region: '' })
  Object.assign(filter, draft)
}

// ---- 新增 / 编辑 ----
const formVisible = ref(false)
const editId = ref(null)
const formRef = ref(null)
const savingForm = ref(false)
const form = reactive({})
const formRules = {
  name: [{ required: true, message: '请输入客户名称', trigger: 'blur' }],
  website: [{ type: 'url', message: '请输入合法的网址（含 http/https）', trigger: 'blur' }],
}

function openForm(id) {
  editId.value = id || null
  Object.keys(form).forEach((k) => delete form[k])
  Object.assign(form, { name: '', website: '', type: '', level: '', region: '', source: '', remark: '' })
  if (id) {
    get(`/customers/${id}`).then((cu) => {
      Object.keys(form).forEach((k) => { form[k] = cu[k] ?? form[k] })
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
    const r = editId.value ? await put(`/customers/${editId.value}`, form) : await post('/customers', form)
    if (r.error) return ElMessage.error(r.error)
    ElMessage.success(editId.value ? '更新成功' : '创建成功')
    formVisible.value = false
    load(); dict.loadCustomers()
  } finally {
    savingForm.value = false
  }
}

async function deleteCustomer(id) {
  try {
    await ElMessageBox.confirm('确认归档该客户？归档后不在列表中显示。', '归档客户', { type: 'warning' })
  } catch (e) { return }
  const r = await del(`/customers/${id}`)
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success('已归档'); load()
}

// ---- 详情（4 tab） ----
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref(null)
const custTab = ref('contacts')
const custActs = ref([])
const actsLoading = ref(false)
const newsLoading = ref(false)

async function viewDetail(id) {
  detailVisible.value = true
  detailLoading.value = true
  custTab.value = 'contacts'
  custActs.value = []
  detail.value = await get(`/customers/${id}`)
  detailLoading.value = false
}

watch(custTab, async (t) => {
  if (!detail.value) return
  const id = detail.value.id
  if (t === 'acts') {
    if (custActs.value.length) return
    actsLoading.value = true
    custActs.value = await getList(`/activities?customer_id=${id}`)
    actsLoading.value = false
  } else {
    // 切回其他 tab 时刷新 contacts/opps/news
    detail.value = await get(`/customers/${id}`)
  }
})

async function collectNews() {
  newsLoading.value = true
  try {
    const r = await post(`/customers/${detail.value.id}/collect-news`)
    if (r.error) return ElMessage.error(r.error)
    ElMessage.success(r.message || '采集完成')
    detail.value = await get(`/customers/${detail.value.id}`)
  } finally {
    newsLoading.value = false
  }
}

async function deleteNews(id) {
  try {
    await ElMessageBox.confirm('确认删除该条采集信息？', '删除动态', { type: 'warning' })
  } catch (e) { return }
  const r = await del(`/news/customer/${id}`)
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success('已删除')
  detail.value = await get(`/customers/${detail.value.id}`)
}

// 跨页跳转改用路由 query（原先写 window._presetOppDetail / window._presetCustomer 全局变量，刷新即丢）
function openOppFromCustomer(oppId) {
  detailVisible.value = false
  router.push({ path: '/opportunities', query: { oppId } })
}
function addActivityFromCustomer() {
  detailVisible.value = false
  router.push({ path: '/contactlog', query: { customerId: detail.value.id } })
}

async function doExport() {
  const err = await exportCsv('customers', filteredList.value)
  err ? ElMessage.error(err) : ElMessage.success(`已导出 ${filteredList.value.length} 条`)
}

onMounted(async () => {
  await Promise.all([load(), dict.loadOptions()])
})
</script>

<style scoped>
.w-full { width: 100%; }
.w-140 { width: 140px; }
.w-200 { width: 200px; }

.detail-body { min-height: 80px; }
.detail-tabs { margin-top: 16px; }
.tab-actions { margin-bottom: 12px; }
.hint { margin-top: 8px; }
</style>
