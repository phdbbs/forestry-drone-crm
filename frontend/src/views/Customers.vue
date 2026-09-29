<template>
  <div class="page">
    <PageHeader title="客户管理" subtitle="客户档案、等级分层与动态情报">
      <template #actions>
        <el-button :icon="Download" plain @click="doExport">导出</el-button>
        <el-button type="primary" :icon="Plus" @click="openForm()">新增客户</el-button>
      </template>
    </PageHeader>

    <FilterBar @search="applyFilter" @reset="resetFilter">
      <el-form-item label="名称">
        <el-input v-model="draft.q" placeholder="搜索客户名称..." clearable style="width:220px" @keyup.enter="applyFilter" />
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="draft.type" clearable placeholder="全部类型" style="width:150px" @change="applyFilter">
          <el-option v-for="t in typeOptions" :key="t" :value="t" :label="t" />
        </el-select>
      </el-form-item>
      <el-form-item label="等级">
        <el-select v-model="draft.level" clearable placeholder="全部等级" style="width:150px" @change="applyFilter">
          <el-option v-for="l in levelOptions" :key="l" :value="l" :label="l" />
        </el-select>
      </el-form-item>
      <el-form-item label="地区">
        <el-input v-model="draft.region" placeholder="如: 浙江" clearable style="width:150px" />
      </el-form-item>
    </FilterBar>

    <div class="table-wrap">
      <PageTable
        storage-key="customer" :data="filteredList" :loading="loading"
        :default-sort="{ prop: 'name', order: 'ascending' }"
        empty-text="暂无客户" empty-hint="新增客户建档，或从线索转化自动创建"
      >
        <template #empty-action>
          <el-button type="primary" plain size="small" :icon="Plus" @click="openForm()" style="margin-top:12px">新增客户</el-button>
        </template>

        <el-table-column prop="id" label="编号" width="86" sortable="custom">
          <template #default="{ row }">
            <span class="mono serial">{{ custNo(row.id) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="客户名称" min-width="230" sortable="custom">
          <template #default="{ row }">
            <div class="name-body">
              <div class="cell-title-text is-link" :title="row.name" @click="viewDetail(row.id)">{{ row.name }}</div>
              <div v-if="row.website" class="cell-meta">{{ shortUrl(row.website) }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="type" label="类型" width="130" sortable="custom">
          <template #default="{ row }">
            <el-tag v-if="row.type" size="small" effect="plain" round>{{ row.type }}</el-tag>
            <span v-else class="dim">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="level" label="等级" width="130" sortable="custom">
          <template #default="{ row }">
            <span v-if="row.level" class="level-pill" :class="`level-pill--${levelKey(row.level)}`">{{ row.level }}</span>
            <span v-else class="dim">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="region" label="地区" width="130" sortable="custom">
          <template #default="{ row }">{{ row.region || '—' }}</template>
        </el-table-column>
        <el-table-column prop="contact_count" label="联系人" width="92" sortable="custom" align="right">
          <template #default="{ row }">
            <span class="mono count">{{ row.contact_count || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" min-width="140" show-overflow-tooltip>
          <template #default="{ row }"><span class="dim">{{ row.source || '—' }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right" align="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button link size="small" @click="openForm(row.id)">编辑</el-button>
              <el-button link type="danger" size="small" @click="deleteCustomer(row.id)">归档</el-button>
            </div>
          </template>
        </el-table-column>
      </PageTable>
    </div>

    <!-- 新增 / 编辑客户 -->
    <el-dialog v-model="formVisible" :title="editId ? '编辑客户' : '新增客户'" width="680px" destroy-on-close class="form-dialog">
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="98px" label-position="right">
        <div class="form-section">
          <div class="section-title">基本信息</div>
          <el-form-item label="客户名称" prop="name">
            <el-input v-model="form.name" placeholder="单位全称" />
          </el-form-item>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="类型">
                <el-select v-model="form.type" clearable placeholder="选填" style="width:100%">
                  <el-option v-for="t in dict.options.customer_types" :key="t" :value="t" :label="t" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="等级">
                <el-select v-model="form.level" clearable placeholder="选填" style="width:100%">
                  <el-option v-for="l in dict.options.customer_levels" :key="l" :value="l" :label="l" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="地区">
                <el-select v-model="form.region" clearable filterable placeholder="选填" style="width:100%">
                  <el-option v-for="r in dict.options.regions" :key="r" :value="r" :label="r" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="来源">
                <el-input v-model="form.source" placeholder="如：展会 / 转介绍" />
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <div class="form-section">
          <div class="section-title">情报</div>
          <el-form-item label="官网" prop="website">
            <el-input v-model="form.website" placeholder="https://...（用于新闻采集）" />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="form.remark" type="textarea" :rows="2" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingForm" @click="saveForm">{{ editId ? '保存修改' : '创建客户' }}</el-button>
      </template>
    </el-dialog>

    <!-- 客户详情（4 tab） -->
    <el-dialog v-model="detailVisible" title="客户详情" width="800px" destroy-on-close class="detail-dialog">
      <div v-loading="detailLoading" class="detail-loading-wrap">
        <template v-if="detail">
          <div class="detail-hero">
            <span class="hero-avatar" :style="{ background: avatarHue(detail.name) }">{{ (detail.name || '?').slice(0, 1) }}</span>
            <div class="detail-hero-body">
              <div class="detail-hero-title">{{ detail.name }}</div>
              <div class="detail-hero-meta">
                <span class="mono hero-serial">{{ custNo(detail.id) }}</span>
                <span v-if="detail.level" class="level-pill" :class="`level-pill--${levelKey(detail.level)}`">{{ detail.level }}</span>
                <el-tag v-if="detail.type" size="small" effect="plain" round>{{ detail.type }}</el-tag>
                <span v-if="detail.region" class="hero-chip">{{ detail.region }}</span>
                <span v-if="detail.contact_count != null" class="muted">{{ detail.contacts?.length ?? detail.contact_count }} 个联系人</span>
              </div>
            </div>
            <div v-if="detail.website" class="detail-hero-side">
              <el-link type="primary" :href="detail.website" target="_blank" :underline="false" class="site-link">
                访问官网 <el-icon :size="11" style="vertical-align:-1px"><TopRight /></el-icon>
              </el-link>
            </div>
          </div>

          <div class="detail-body">
            <el-tabs v-model="custTab" class="cust-tabs">
              <!-- 联系人 -->
              <el-tab-pane :label="`联系人 (${(detail.contacts || []).length})`" name="contacts">
                <el-table v-if="(detail.contacts || []).length" :data="detail.contacts" size="small">
                  <el-table-column prop="name" label="姓名" width="110">
                    <template #default="{ row }"><span class="strong">{{ row.name }}</span></template>
                  </el-table-column>
                  <el-table-column prop="title" label="职务" min-width="130" show-overflow-tooltip />
                  <el-table-column prop="phone" label="电话" width="150">
                    <template #default="{ row }"><span class="mono">{{ row.phone || '—' }}</span></template>
                  </el-table-column>
                  <el-table-column label="重要度" width="90">
                    <template #default="{ row }">
                      <el-tag v-if="row.importance" size="small" type="warning" effect="plain" round>{{ row.importance }}</el-tag>
                      <span v-else class="dim">—</span>
                    </template>
                  </el-table-column>
                </el-table>
                <div v-else class="list-empty muted">暂无联系人，可在「联系人」模块补充</div>
              </el-tab-pane>

              <!-- 商机 -->
              <el-tab-pane :label="`商机 (${(detail.opportunities || []).length})`" name="opps">
                <template v-if="(detail.opportunities || []).length">
                  <el-table :data="detail.opportunities" size="small">
                    <el-table-column label="商机名称" min-width="220">
                      <template #default="{ row }">
                        <el-link type="primary" :underline="false" @click="openOppFromCustomer(row.id)">{{ row.title }}</el-link>
                      </template>
                    </el-table-column>
                    <el-table-column label="金额(万)" width="100" align="right">
                      <template #default="{ row }"><span class="mono">{{ fmtNum(row.amount) }}</span></template>
                    </el-table-column>
                    <el-table-column label="阶段" width="110">
                      <template #default="{ row }"><span class="stage-chip">{{ row.current_stage || '—' }}</span></template>
                    </el-table-column>
                    <el-table-column label="赢率" width="80" align="right">
                      <template #default="{ row }"><span class="mono">{{ row.probability || 20 }}%</span></template>
                    </el-table-column>
                  </el-table>
                  <div class="muted hint">点击商机名称跳转到商机管理查看详情</div>
                </template>
                <div v-else class="list-empty muted">该客户暂无商机</div>
              </el-tab-pane>

              <!-- 联络记录 -->
              <el-tab-pane label="联络记录" name="acts">
                <div class="tab-toolbar">
                  <el-button type="primary" plain size="small" :icon="Plus" @click="addActivityFromCustomer">新增日常联络</el-button>
                </div>
                <el-table :data="custActs" size="small" v-loading="actsLoading">
                  <el-table-column label="时间" width="110">
                    <template #default="{ row }"><span class="mono">{{ fmtDate(row.activity_time) || '—' }}</span></template>
                  </el-table-column>
                  <el-table-column label="联系人" width="100">
                    <template #default="{ row }">{{ row.contact_name || '—' }}</template>
                  </el-table-column>
                  <el-table-column label="内容" min-width="240" show-overflow-tooltip>
                    <template #default="{ row }">{{ row.content || '—' }}</template>
                  </el-table-column>
                  <el-table-column label="预计联系" width="110">
                    <template #default="{ row }"><span class="mono muted">{{ fmtDate(row.next_followup_time) || '—' }}</span></template>
                  </el-table-column>
                </el-table>
                <div v-if="!custActs.length && !actsLoading" class="list-empty muted">暂无联络记录</div>
              </el-tab-pane>

              <!-- 动态信息 -->
              <el-tab-pane :label="`动态信息 (${(detail.news || []).length})`" name="news">
                <div class="tab-toolbar">
                  <el-button type="primary" plain size="small" :icon="Lightning" :loading="newsLoading" @click="collectNews">采集新闻</el-button>
                  <span class="muted hint-inline" v-if="!detail.website">先补充客户官网，才能采集动态</span>
                </div>
                <el-table v-if="(detail.news || []).length" :data="detail.news" size="small">
                  <el-table-column label="采集时间" width="110">
                    <template #default="{ row }"><span class="mono">{{ fmtDate(row.date) || '—' }}</span></template>
                  </el-table-column>
                  <el-table-column label="来源" width="140" show-overflow-tooltip>
                    <template #default="{ row }">{{ row.source_name || '—' }}</template>
                  </el-table-column>
                  <el-table-column label="新闻标题" min-width="260">
                    <template #default="{ row }">
                      <div class="news-title">{{ row.title }}</div>
                      <div v-if="row.content" class="news-snippet muted">{{ row.content.slice(0, 80) }}</div>
                    </template>
                  </el-table-column>
                  <el-table-column label="事件时间" width="110">
                    <template #default="{ row }"><span class="mono muted">{{ row.event_time || '—' }}</span></template>
                  </el-table-column>
                  <el-table-column label="操作" width="70" align="right">
                    <template #default="{ row }">
                      <el-button link type="danger" size="small" @click="deleteNews(row.id)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>
                <div v-else class="list-empty muted">暂无动态信息，点击「采集新闻」抓取自官网与媒体</div>
              </el-tab-pane>
            </el-tabs>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <template v-if="detail">
          <el-button @click="quickNewContact">
            <el-icon><Plus /></el-icon>&nbsp;新增联系人
          </el-button>
          <el-button @click="quickNewOpp">
            <el-icon><Plus /></el-icon>&nbsp;新建商机
          </el-button>
        </template>
        <el-button v-if="detail" type="primary" @click="openForm(detail.id)">编辑客户</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Download, Lightning, TopRight } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import PageTable from '../components/PageTable.vue'
import FilterBar from '../components/FilterBar.vue'
import { get, getList, post, put, del, fmtDate, fmtNum, exportCsv } from '../api'
import { useFilterMemory } from '../composables/useFilterMemory'
import { useDictStore } from '../stores/app'

const dict = useDictStore()
const route = useRoute()
const router = useRouter()
const custNo = (id) => (id === null || id === undefined ? '—' : String(id).padStart(6, '0'))
const TYPE_OPTIONS = ['政府部门', '事业单位', '国有企业', '民营企业', '科研院所', '运营商', '科技公司']
const LEVEL_OPTIONS = ['A-重点客户', 'B-重要客户', 'C-一般客户', 'D-潜在客户']
const typeOptions = computed(() => (dict.options.customer_types?.length ? dict.options.customer_types : TYPE_OPTIONS))
const levelOptions = computed(() => (dict.options.customer_levels?.length ? dict.options.customer_levels : LEVEL_OPTIONS))

const levelKey = (lv) => (/A/.test(lv) ? 'a' : /B/.test(lv) ? 'b' : /C/.test(lv) ? 'c' : 'd')
// 稳定色相：同名客户颜色一致，作为头像底色
const avatarHue = (name) => {
  let h = 0
  for (const ch of name || '?') h = (h * 31 + ch.codePointAt(0)) % 360
  return `linear-gradient(135deg, hsl(${h} 38% 52%), hsl(${(h + 40) % 360} 42% 42%))`
}
const shortUrl = (u) => (u || '').replace(/^https?:\/\//, '').replace(/\/$/, '')

const customers = ref([])
const loading = ref(false)
const filter = useFilterMemory('customers', { q: '', type: '', level: '', region: '' })
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
  const r = await get(`/customers/${id}`)
  if (!r || r.error) return ElMessage.error('加载客户详情失败：' + ((r && r.error) || '请稍后重试'))
  custTab.value = 'contacts'
  custActs.value = []
  detail.value = r
  detailVisible.value = true
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
    const fresh = await get(`/customers/${id}`)
    if (fresh && !fresh.error) detail.value = fresh
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

function quickNewContact() {
  detailVisible.value = false
  router.push({ path: '/contacts', query: { new: 1, customerId: detail.value.id } })
}
function quickNewOpp() {
  detailVisible.value = false
  router.push({ path: '/opportunities', query: { new: 1, customerId: detail.value.id } })
}
async function doExport() {
  const err = await exportCsv('customers', filteredList.value)
  err ? ElMessage.error(err) : ElMessage.success(`已导出 ${filteredList.value.length} 条`)
}

onMounted(async () => {
  await Promise.all([load(), dict.loadOptions()])
  // 全局搜索直达：?detail=<id> 打开客户详情
  if (route.query.detail) viewDetail(Number(route.query.detail))
})
</script>

<style scoped>
/* ---- 表格容器 ---- */
.table-wrap {
  background: var(--crm-bg-card);
  border: 1px solid var(--crm-border-soft);
  border-radius: var(--crm-radius-lg);
  overflow: hidden;
  box-shadow: var(--crm-shadow-xs);
}

/* ---- 单元格 ---- */
.cell-name { display: flex; align-items: center; gap: 10px; min-width: 0; }
.name-avatar {
  width: 30px; height: 30px; border-radius: 8px; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  color: #fff; font-size: 13.5px; font-weight: 600;
  font-family: var(--crm-font-display);
}
.name-body { min-width: 0; }
.cell-title-text {
  color: var(--crm-fg-1); font-weight: 500; font-size: 13.5px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.cell-title-text.is-link {
  cursor: pointer; text-decoration: underline;
  text-underline-offset: 2px; text-decoration-thickness: 1px;
  text-decoration-color: var(--crm-border-strong);
}
.cell-title-text.is-link:hover { color: var(--crm-pine-600); text-decoration-color: var(--crm-pine-600); }
.serial { font-size: 12px; color: var(--crm-fg-3); letter-spacing: 0.01em; }
.hero-serial {
  padding: 1px 8px; border-radius: var(--crm-radius-sm);
  background: var(--crm-slate-100); color: var(--crm-fg-2); font-size: 12px;
}
.cell-meta {
  font-size: 11.5px; color: var(--crm-fg-4); margin-top: 2px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.count { font-size: 12.5px; font-weight: 600; color: var(--crm-fg-2); }
.row-actions { display: inline-flex; gap: 0; justify-content: flex-end; align-items: center; }
.row-actions :deep(.el-button.is-link) { padding: 2px 6px; }

/* ---- 等级胶囊 ---- */
.level-pill {
  display: inline-flex; align-items: center;
  padding: 2px 8px;
  font-size: 11.5px; font-weight: 500;
  border-radius: var(--crm-radius-full);
  white-space: nowrap;
}
.level-pill--a { background: var(--crm-rose-50, #fef2f2); color: var(--crm-rose-500); }
.level-pill--b { background: var(--crm-amber-50); color: var(--crm-amber-500); }
.level-pill--c { background: var(--crm-pine-25); color: var(--crm-pine-600); }
.level-pill--d { background: var(--crm-slate-100); color: var(--crm-fg-3); }

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
.hero-avatar {
  width: 44px; height: 44px; border-radius: 12px; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  color: #fff; font-size: 19px; font-weight: 600;
  font-family: var(--crm-font-display);
  box-shadow: var(--crm-shadow-sm);
}
.detail-hero-body { flex: 1; min-width: 0; }
.detail-hero-title {
  font-family: var(--crm-font-display);
  font-size: 16px; font-weight: 600; color: var(--crm-fg-1);
  line-height: 1.4; letter-spacing: -0.011em;
  margin-bottom: 6px;
  word-break: break-word; overflow-wrap: anywhere;
}
.detail-hero-meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 12px; color: var(--crm-fg-3); }
.hero-chip {
  padding: 1px 8px; border-radius: var(--crm-radius-sm);
  background: var(--crm-slate-100); color: var(--crm-fg-2); font-size: 12px;
}
.detail-hero-side { flex-shrink: 0; }
.site-link { font-size: 12.5px; }

.detail-body { padding: 8px 24px 8px; }
.cust-tabs :deep(.el-tabs__header) { margin-bottom: 12px; }
.tab-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.hint { margin-top: 8px; font-size: 12px; }
.hint-inline { font-size: 12px; }
.list-empty { padding: 26px 0; text-align: center; font-size: 12.5px; }
.strong { font-weight: 500; color: var(--crm-fg-1); }
.stage-chip {
  display: inline-block; padding: 1px 8px;
  font-size: 11.5px; border-radius: var(--crm-radius-full);
  background: var(--crm-slate-100); color: var(--crm-fg-2);
}
.news-title { font-size: 13px; color: var(--crm-fg-1); line-height: 1.5; }
.news-snippet { font-size: 11.5px; margin-top: 2px; line-height: 1.5; }

@media (max-width: 768px) {
  .detail-hero { padding: 16px 18px; }
  .detail-body { padding: 4px 18px 0; }
  .detail-hero-side { display: none; }
}
</style>
