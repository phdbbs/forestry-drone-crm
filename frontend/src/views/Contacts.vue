<template>
  <div class="page">
    <PageHeader title="联系人管理" subtitle="关键决策人画像与关系资产">
      <template #actions>
        <el-button :icon="Download" plain @click="doExport">导出</el-button>
        <el-button type="primary" :icon="Plus" @click="openForm()">新增联系人</el-button>
      </template>
    </PageHeader>

    <FilterBar @search="applyFilter" @reset="resetFilter">
      <el-form-item label="姓名/职位">
        <el-input v-model="draft.q" placeholder="搜索姓名或职位..." clearable style="width:220px" @keyup.enter="applyFilter" />
      </el-form-item>
      <el-form-item label="所属客户">
        <el-select v-model="draft.customer" clearable filterable placeholder="全部客户" style="width:200px" @change="applyFilter">
          <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
        </el-select>
      </el-form-item>
      <el-form-item label="角色">
        <el-select v-model="draft.role" clearable placeholder="全部角色" style="width:150px" @change="applyFilter">
          <el-option v-for="r in ROLE_OPTIONS" :key="r" :value="r" :label="r" />
        </el-select>
      </el-form-item>
    </FilterBar>

    <div class="table-wrap">
      <PageTable
        storage-key="contact" :data="filteredList" :loading="loading"
        :default-sort="{ prop: 'name', order: 'ascending' }"
        empty-text="暂无联系人" empty-hint="建档联系人，沉淀关键决策链关系"
      >
        <template #empty-action>
          <el-button type="primary" plain size="small" :icon="Plus" @click="openForm()" style="margin-top:12px">新增联系人</el-button>
        </template>

        <el-table-column prop="id" label="编号" width="86" sortable="custom">
          <template #default="{ row }">
            <span class="mono serial">{{ ctNo(row.id) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="姓名" min-width="150" sortable="custom">
          <template #default="{ row }">
            <div class="p-body">
              <div class="cell-title-text is-link" :title="row.name" @click="viewDetail(row.id)">{{ row.name }}</div>
              <div v-if="row.title" class="cell-meta">{{ row.title }}</div>
              <div v-if="staleDays(row.last_activity_at) !== null" class="cell-meta stale-tag" :class="{ 'is-hot': staleDays(row.last_activity_at) >= 30 }">已 {{ staleDays(row.last_activity_at) }} 天未联络</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="customer_name" label="所属客户" min-width="170" sortable="custom" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.customer_name">{{ row.customer_name }}</span>
            <span v-else class="dim">未关联</span>
          </template>
        </el-table-column>
        <el-table-column prop="phone" label="电话" width="140" sortable="custom">
          <template #default="{ row }">
            <CopyText v-if="row.phone" :value="row.phone" tel class="mono" />
            <span v-else class="dim">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="wechat" label="微信号" width="110" show-overflow-tooltip>
          <template #default="{ row }"><span class="muted">{{ row.wechat || '—' }}</span></template>
        </el-table-column>
        <el-table-column prop="role" label="角色" width="106" sortable="custom">
          <template #default="{ row }">
            <el-tag v-if="row.role" size="small" effect="plain" round>{{ row.role }}</el-tag>
            <span v-else class="dim">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="importance" label="重要性" width="100" sortable="custom">
          <template #default="{ row }">
            <span v-if="row.importance" class="imp-pill">
              <el-icon :size="10" class="imp-star"><StarFilled /></el-icon>{{ row.importance }}
            </span>
            <span v-else class="dim">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right" align="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button link size="small" @click="openForm(row.id)">编辑</el-button>
              <el-button link type="danger" size="small" @click="deleteContact(row.id)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </PageTable>
    </div>

    <!-- 新增 / 编辑联系人 -->
    <el-dialog v-model="formVisible" :title="editId ? '编辑联系人' : '新增联系人'" width="700px" destroy-on-close class="form-dialog">
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="92px" label-position="right">
        <div class="form-section">
          <div class="section-title">基本信息</div>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="姓名" prop="name">
                <el-input v-model="form.name" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="职位">
                <el-input v-model="form.title" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="角色">
                <el-select v-model="form.role" clearable placeholder="选填" style="width:100%">
                  <el-option v-for="r in ROLE_OPTIONS" :key="r" :value="r" :label="r" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="所属客户">
                <el-select v-model="form.customer_id" clearable filterable placeholder="从客户库选择" style="width:100%">
                  <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <div class="form-section">
          <div class="section-title">联系方式</div>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="电话" prop="phone">
                <el-input v-model="form.phone" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="邮箱" prop="email">
                <el-input v-model="form.email" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="微信号">
                <el-input v-model="form.wechat" placeholder="微信号，详情页同一字段" />
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <div class="form-section">
          <div class="section-title">画像</div>
          <el-form-item label="标签">
            <el-input v-model="form.tags" placeholder="逗号分隔，如: 高层,关键决策" />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="form.notes" type="textarea" :rows="2" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingForm" @click="saveForm">{{ editId ? '保存修改' : '创建联系人' }}</el-button>
      </template>
    </el-dialog>

    <!-- 联系人详情 + 动态 -->
    <el-dialog v-model="detailVisible" title="联系人详情" width="780px" destroy-on-close class="detail-dialog">
      <div v-loading="detailLoading" class="detail-loading-wrap">
        <template v-if="detail">
          <div class="detail-hero">
            <span class="hero-avatar" :style="{ background: avatarHue(detail.name) }">{{ (detail.name || '?').slice(0, 1) }}</span>
            <div class="detail-hero-body">
              <div class="detail-hero-title">
                {{ detail.name }}
                <span v-if="detail.importance" class="imp-pill">
                  <el-icon :size="10" class="imp-star"><StarFilled /></el-icon>{{ detail.importance }}
                </span>
              </div>
              <div class="detail-hero-meta">
                <span class="mono hero-serial">{{ ctNo(detail.id) }}</span>
                <span v-if="detail.title" class="hero-chip">{{ detail.title }}</span>
                <el-tag v-if="detail.role" size="small" effect="plain" round>{{ detail.role }}</el-tag>
                <span v-if="detail.customer_name" class="muted">{{ detail.customer_name }}</span>
              </div>
            </div>
          </div>

          <div class="detail-body">
            <div class="section-title">联系方式与画像</div>
            <DetailGrid :items="[
              { label: '电话', value: detail.phone, mono: true, slot: 'phone' },
              { label: '邮箱', value: detail.email, mono: true },
              { label: '微信号', value: detail.wechat },
              { label: '重要性', value: detail.importance },
              { label: '分管业务', value: detail.business_scope, full: true },
              { label: '标签', value: detail.tags, full: true },
              { label: '备注', value: detail.notes, full: true, slot: 'notes' },
            ]" >
  <template #phone="{ item }"><CopyText :value="item.value" tel /></template>
  <template #notes="{ item }">
    <div v-if="item.value" class="notes-text">{{ item.value }}</div>
    <div v-if="detail.lead" class="lead-ref">
      <span>由线索{{ detail.lead.serial_no ? ` ${detail.lead.serial_no} ` : ' ' }}创建：{{ detail.lead.title }}</span>
      <el-link
        v-if="isWinLead && detail.lead.source_url" type="primary"
        :href="detail.lead.source_url" target="_blank" :underline="false" class="bid-link"
      >招标链接</el-link>
    </div>
    <span v-if="!item.value && !detail.lead" class="muted">—</span>
  </template>
</DetailGrid>

            <div class="section-title">动态信息</div>
            <el-tabs v-model="ctTab" class="ct-tabs">
              <!-- 联络记录 -->
              <el-tab-pane :label="`联络记录 (${ctActs.length})`" name="acts">
                <el-table v-loading="actsLoading" :data="ctActs" size="small">
                  <el-table-column label="时间" width="140">
                    <template #default="{ row }"><span class="mono">{{ fmtDate(row.activity_time) || '—' }}</span></template>
                  </el-table-column>
                  <el-table-column label="方式" width="80">
                    <template #default="{ row }">{{ row.method || '—' }}</template>
                  </el-table-column>
                  <el-table-column label="内容" min-width="220" show-overflow-tooltip>
                    <template #default="{ row }">{{ row.content || '—' }}</template>
                  </el-table-column>
                  <el-table-column label="商机" width="150" show-overflow-tooltip>
                    <template #default="{ row }">
                      <el-link v-if="row.opportunity_id" type="primary" :underline="false" @click="openOpp(row.opportunity_id)">
                        {{ row.opportunity_title || '查看商机' }}
                      </el-link>
                      <span v-else class="dim">—</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作用户" width="96">
                    <template #default="{ row }">{{ row.operator || '系统' }}</template>
                  </el-table-column>
                </el-table>
                <div v-if="!ctActs.length && !actsLoading" class="list-empty muted">暂无联络记录</div>
              </el-tab-pane>

              <!-- 联络计划 -->
              <el-tab-pane :label="`联络计划 (${ctPlans.length})`" name="plans">
                <el-table v-loading="plansLoading" :data="ctPlans" size="small">
                  <el-table-column label="计划时间" width="110">
                    <template #default="{ row }"><span class="mono">{{ fmtDate(row.plan_date) || '—' }}</span></template>
                  </el-table-column>
                  <el-table-column label="状态" width="80">
                    <template #default="{ row }">
                      <el-tag :type="row.actual_date ? 'success' : 'warning'" size="small" effect="plain" round>
                        {{ row.actual_date ? '已完成' : '待执行' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="内容" min-width="220" show-overflow-tooltip>
                    <template #default="{ row }">{{ row.actual_content || row.content || '—' }}</template>
                  </el-table-column>
                  <el-table-column label="商机" width="150" show-overflow-tooltip>
                    <template #default="{ row }">
                      <el-link v-if="row.opportunity_id" type="primary" :underline="false" @click="openOpp(row.opportunity_id)">
                        {{ row.opportunity_title || '查看商机' }}
                      </el-link>
                      <span v-else class="dim">—</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作用户" width="96">
                    <template #default="{ row }">{{ row.executed_by || row.operator || '系统' }}</template>
                  </el-table-column>
                </el-table>
                <div v-if="!ctPlans.length && !plansLoading" class="list-empty muted">暂无联络计划</div>
              </el-tab-pane>

              <!-- 关联商机 -->
              <el-tab-pane :label="`关联商机 (${(detail.opportunities || []).length})`" name="opps">
                <el-table v-if="(detail.opportunities || []).length" :data="detail.opportunities" size="small">
                  <el-table-column label="商机名称" min-width="220">
                    <template #default="{ row }">
                      <el-link type="primary" :underline="false" @click="openOpp(row.id)">{{ row.title }}</el-link>
                    </template>
                  </el-table-column>
                  <el-table-column label="金额(万)" width="100" align="right">
                    <template #default="{ row }"><span class="mono">{{ row.amount || '—' }}</span></template>
                  </el-table-column>
                  <el-table-column label="阶段" width="110">
                    <template #default="{ row }">{{ row.current_stage || '—' }}</template>
                  </el-table-column>
                  <el-table-column label="创建" width="110">
                    <template #default="{ row }"><span class="mono muted">{{ fmtDate(row.created_at) || '—' }}</span></template>
                  </el-table-column>
                </el-table>
                <div v-else class="list-empty muted">该联系人暂无关联商机</div>
              </el-tab-pane>

              <!-- 动态信息（新闻采集） -->
              <el-tab-pane :label="`动态 (${(detail.contact_news || []).length})`" name="news">
                <div class="tab-toolbar">
                  <el-button type="primary" plain size="small" :icon="Lightning" :loading="newsLoading" @click="collectNews">
                    采集
                  </el-button>
                  <span class="muted hint-inline">按姓名匹配官网 / 媒体提及</span>
                </div>

                <div v-if="(detail.contact_news || []).length" class="news-list">
                  <div v-for="n in detail.contact_news" :key="n.id" class="news-item">
                    <div class="news-main">
                      <el-link v-if="n.url" type="primary" :href="n.url" target="_blank" :underline="false" class="news-title">
                        {{ n.title }}
                      </el-link>
                      <div v-else class="news-title">{{ n.title }}</div>
                      <div v-if="n.summary" class="news-summary muted">{{ n.summary }}</div>
                      <div class="news-meta mono">
                        {{ n.source_name || '未知来源' }}<span v-if="n.event_time"> · 事件 {{ n.event_time }}</span>
                        · 采集于 {{ fmtDate(n.crawled_at) || '—' }}
                      </div>
                    </div>
                    <el-button link type="danger" size="small" @click="deleteNews(n.id)">删除</el-button>
                  </div>
                </div>
                <div v-else class="list-empty muted">暂无动态信息，点击「采集」（按姓名匹配官网/媒体新闻）</div>
              </el-tab-pane>
            </el-tabs>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button v-if="detail" @click="quickLog">
          <el-icon><Phone /></el-icon>&nbsp;记一笔联络
        </el-button>
        <el-button v-if="detail" type="primary" @click="openForm(detail.id)">编辑联系人</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Download, Lightning, StarFilled, Phone } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'
import PageTable from '../components/PageTable.vue'
import FilterBar from '../components/FilterBar.vue'
import CopyText from '../components/CopyText.vue'
import DetailGrid from '../components/DetailGrid.vue'
import { get, getList, post, put, del, fmtDate, exportCsv, ROLE_OPTIONS } from '../api'
import { useFilterMemory } from '../composables/useFilterMemory'
import { useDictStore } from '../stores/app'

const dict = useDictStore()
const route = useRoute()
const router = useRouter()
const contacts = ref([])
const loading = ref(false)
const ctNo = (id) => (id === null || id === undefined ? '—' : String(id).padStart(6, '0'))
const filter = useFilterMemory('contacts', { q: '', customer: '', role: '' })
const draft = reactive({ ...filter })  // 初值取记忆条件，别让输入框与生效条件脱节

// 稳定色相：同名联系人头像底色一致
const avatarHue = (name) => {
  let h = 0
  for (const ch of name || '?') h = (h * 31 + ch.codePointAt(0)) % 360
  return `linear-gradient(135deg, hsl(${h} 38% 52%), hsl(${(h + 40) % 360} 42% 42%))`
}

const filteredList = computed(() => contacts.value.filter((ct) => {
  const q = (filter.q || '').toLowerCase()
  if (q && !(ct.name || '').toLowerCase().includes(q) && !(ct.title || '').toLowerCase().includes(q)) return false
  if (filter.customer && String(ct.customer_id) !== String(filter.customer)) return false
  if (filter.role && ct.role !== filter.role) return false
  return true
}))

async function load() {
  loading.value = true
  contacts.value = await getList('/contacts')
  loading.value = false
}
function applyFilter() { Object.assign(filter, draft) }
function resetFilter() {
  Object.assign(draft, { q: '', customer: '', role: '' })
  Object.assign(filter, draft)
}

// ---- 新增 / 编辑 ----
const formVisible = ref(false)
const editId = ref(null)
const formRef = ref(null)
const savingForm = ref(false)
const form = reactive({})
const formRules = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  phone: [{ pattern: /^[\d\-+() ]*$/, message: '电话格式不正确', trigger: 'blur' }],
  email: [{ type: 'email', message: '邮箱格式不正确', trigger: 'blur' }],
}

function openForm(id) {
  editId.value = id || null
  Object.keys(form).forEach((k) => delete form[k])
  Object.assign(form, { name: '', title: '', phone: '', email: '', wechat: '', role: '', tags: '', customer_id: null, importance: '', notes: '' })
  if (id) {
    get(`/contacts/${id}`).then((ct) => {
      Object.keys(form).forEach((k) => { form[k] = ct[k] ?? form[k] })
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
    const r = editId.value ? await put(`/contacts/${editId.value}`, form) : await post('/contacts', form)
    if (r.error) return ElMessage.error(r.error)
    ElMessage.success(editId.value ? '更新成功' : '创建成功')
    formVisible.value = false
    load(); dict.loadContacts()
  } finally {
    savingForm.value = false
  }
}

async function deleteContact(id) {
  try {
    await ElMessageBox.confirm('确认删除该联系人？', '删除联系人', { type: 'warning' })
  } catch (e) { return }
  const r = await del(`/contacts/${id}`)
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success('已删除'); load(); dict.loadContacts()
}

// ---- 详情 + 动态 ----
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref(null)
const newsLoading = ref(false)
const ctTab = ref('acts')
const ctActs = ref([])
const ctPlans = ref([])
const actsLoading = ref(false)
const plansLoading = ref(false)

// 只有中标/成交类公告才在备注里给招标链接（与线索转化弹窗的判定口径一致）
const isWinLead = computed(() => /中标|成交/.test(detail.value?.lead?.bid_type || ''))

async function viewDetail(id) {
  const r = await get(`/contacts/${id}`)
  if (!r || r.error) return ElMessage.error('加载联系人详情失败：' + ((r && r.error) || '请稍后重试'))
  ctTab.value = 'acts'
  ctActs.value = []
  ctPlans.value = []
  detail.value = r
  detailVisible.value = true
}

// 联络记录/计划只在切到对应标签时才拉，打开详情不用一次性打三个接口
watch(ctTab, async (t) => {
  const id = detail.value?.id
  if (!id) return
  if (t === 'acts' && !ctActs.value.length) {
    actsLoading.value = true
    ctActs.value = await getList(`/activities?contact_id=${id}`)
    actsLoading.value = false
  } else if (t === 'plans' && !ctPlans.value.length) {
    plansLoading.value = true
    ctPlans.value = await getList(`/followups?contact_id=${id}`)
    plansLoading.value = false
  }
})

function openOpp(id) {
  detailVisible.value = false
  router.push({ path: '/opportunities', query: { detail: id } })
}

async function collectNews() {
  newsLoading.value = true
  try {
    const r = await post(`/contacts/${detail.value.id}/collect-news`)
    if (r.error) return ElMessage.error(r.error)
    ElMessage.success(r.message || '采集完成')
    detail.value = await get(`/contacts/${detail.value.id}`)
  } finally {
    newsLoading.value = false
  }
}

async function deleteNews(id) {
  try {
    await ElMessageBox.confirm('确认删除该条动态？', '删除动态', { type: 'warning' })
  } catch (e) { return }
  const r = await del(`/news/contact/${id}`)
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success('已删除')
  detail.value = await get(`/contacts/${detail.value.id}`)
}

function quickLog() {
  detailVisible.value = false
  router.push({ path: '/contactlog', query: { new: 1, customerId: detail.value.customer_id, contactId: detail.value.id } })
}
function staleDays(lastAt) {
  if (!lastAt) return null
  const days = Math.floor((Date.now() - new Date(lastAt).getTime()) / 86400000)
  return days >= 14 ? days : null
}
async function doExport() {
  const err = await exportCsv('contacts', filteredList.value)
  err ? ElMessage.error(err) : ElMessage.success(`已导出 ${filteredList.value.length} 条`)
}

onMounted(async () => {
  await Promise.all([load(), dict.loadCustomers()])
  // 客户详情"新增联系人"直达：预选客户
  if (route.query.new && route.query.customerId) {
    openForm()
    form.customer_id = Number(route.query.customerId)
  }
  // 全局搜索直达：?detail=<id> 打开联系人详情
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
.cell-person { display: flex; align-items: center; gap: 10px; min-width: 0; }
.p-avatar {
  width: 30px; height: 30px; border-radius: 50%; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  color: #fff; font-size: 13px; font-weight: 600;
  font-family: var(--crm-font-display);
}
.p-body { min-width: 0; }
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
.row-actions { display: inline-flex; gap: 0; justify-content: flex-end; align-items: center; }
.row-actions :deep(.el-button.is-link) { padding: 2px 6px; }

.imp-pill {
  display: inline-flex; align-items: center; gap: 3px;
  padding: 1px 8px; font-size: 11.5px; font-weight: 500;
  border-radius: var(--crm-radius-full);
  background: var(--crm-amber-50); color: var(--crm-amber-500);
}
.imp-star { color: var(--crm-amber-500); }

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
  width: 44px; height: 44px; border-radius: 50%; flex-shrink: 0;
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
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.detail-hero-meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 12px; color: var(--crm-fg-3); }
.hero-chip {
  padding: 1px 8px; border-radius: var(--crm-radius-sm);
  background: var(--crm-slate-100); color: var(--crm-fg-2); font-size: 12px;
}
.detail-body { padding: 20px 24px 8px; }

.tab-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.hint-inline { font-size: 12px; }

/* 备注里的来源线索：正文 + 可点的招标公告链接 */
.notes-text { line-height: 1.65; }
.lead-ref {
  display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap;
  margin-top: 4px; font-size: 12.5px; color: var(--crm-fg-3);
}
.bid-link { font-size: 12.5px; }
.ct-tabs :deep(.el-tabs__header) { margin-bottom: 8px; }

/* 动态列表 */
.news-list { display: flex; flex-direction: column; }
.news-item {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 11px 2px;
  border-bottom: 1px solid var(--crm-border-soft);
}
.news-item:last-child { border-bottom: none; }
.news-main { flex: 1; min-width: 0; }
.news-title { font-size: 13px; font-weight: 500; color: var(--crm-fg-1); line-height: 1.5; word-break: break-word; }
.news-summary { font-size: 12px; line-height: 1.55; margin-top: 3px; }
.news-meta { font-size: 11px; color: var(--crm-fg-4); margin-top: 5px; }
.list-empty { padding: 26px 0; text-align: center; font-size: 12.5px; }

@media (max-width: 768px) {
  .detail-hero { padding: 16px 18px; }
  .detail-body { padding: 16px 18px 0; }
}
</style>

<style scoped>
.stale-tag { font-size: 11.5px; color: var(--crm-amber-500, #b45309); margin-top: 2px; }
.stale-tag.is-hot { color: var(--crm-rose-500, #b91c1c); }
</style>
