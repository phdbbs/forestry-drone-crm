<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">联系人管理</h2>
      <div class="page-toolbar">
        <el-button :icon="Download" @click="doExport">导出</el-button>
        <el-button type="primary" :icon="Plus" @click="openForm()">新增联系人</el-button>
      </div>
    </div>

    <FilterBar @search="applyFilter" @reset="resetFilter">
      <el-form-item label="姓名/职位">
        <el-input v-model="draft.q" placeholder="搜索姓名或职位..." clearable class="w-200" />
      </el-form-item>
      <el-form-item label="所属客户">
        <el-select v-model="draft.customer" clearable filterable class="w-180" @change="applyFilter">
          <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
        </el-select>
      </el-form-item>
      <el-form-item label="角色">
        <el-select v-model="draft.role" clearable class="w-140" @change="applyFilter">
          <el-option v-for="r in ROLE_OPTIONS" :key="r" :value="r" :label="r" />
        </el-select>
      </el-form-item>
    </FilterBar>

    <el-card shadow="never" body-class="p-0">
      <PageTable storage-key="contact" :data="filteredList" :loading="loading" :default-sort="{ prop: 'name', order: 'ascending' }">
        <el-table-column prop="name" label="姓名" min-width="100" sortable="custom" class-name="cell-strong" />
        <el-table-column prop="title" label="职位" min-width="110" sortable="custom" show-overflow-tooltip />
        <el-table-column prop="customer_name" label="所属客户" min-width="150" sortable="custom" show-overflow-tooltip />
        <el-table-column prop="phone" label="电话" width="128" sortable="custom" />
        <el-table-column prop="wechat" label="微信" width="104" show-overflow-tooltip />
        <el-table-column prop="role" label="角色" width="96" sortable="custom">
          <template #default="{ row }">
            <el-tag v-if="row.role" size="small" effect="light">{{ row.role }}</el-tag>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="importance" label="重要性" width="92" sortable="custom">
          <template #default="{ row }">
            <span :class="{ 'is-important': row.importance }">{{ row.importance || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewDetail(row.id)">查看</el-button>
            <el-button link type="primary" size="small" @click="openForm(row.id)">编辑</el-button>
            <el-button link type="danger" size="small" @click="deleteContact(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </PageTable>
    </el-card>

    <!-- 新增 / 编辑联系人 -->
    <el-dialog v-model="formVisible" :title="editId ? '编辑联系人' : '新增联系人'" width="600px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px">
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
            <el-form-item label="角色">
              <el-select v-model="form.role" clearable class="w-full">
                <el-option v-for="r in ROLE_OPTIONS" :key="r" :value="r" :label="r" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属客户">
              <el-select v-model="form.customer_id" clearable filterable class="w-full">
                <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="标签">
          <el-input v-model="form.tags" placeholder="逗号分隔，如: 高层,关键决策" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingForm" @click="saveForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 联系人详情 + 动态 -->
    <el-dialog v-model="detailVisible" :title="detail?.name || '联系人详情'" width="760px" destroy-on-close>
      <div v-loading="detailLoading" class="detail-body">
        <template v-if="detail">
          <DetailGrid :items="[
            { label: '职位', value: detail.title },
            { label: '所属客户', value: detail.customer_name },
            { label: '电话', value: detail.phone },
            { label: '邮箱', value: detail.email },
            { label: '微信', value: detail.wechat },
            { label: '重要性', value: detail.importance },
            { label: '分管业务', value: detail.business_scope },
            { label: '标签', value: detail.tags },
          ]" />

          <el-alert v-if="detail.notes" class="notes-alert" type="info" :closable="false" :title="`备注：${detail.notes}`" />

          <el-divider content-position="left">
            动态信息（官网/媒体提及）
          </el-divider>
          <el-space class="tab-actions">
            <el-button type="primary" size="small" :icon="Lightning" :loading="newsLoading" @click="collectNews">采集</el-button>
          </el-space>

          <el-table v-if="(detail.contact_news || []).length" :data="detail.contact_news" size="small">
            <el-table-column label="采集时间" width="100">
              <template #default="{ row }">{{ fmtDate(row.crawled_at) || '-' }}</template>
            </el-table-column>
            <el-table-column label="来源" width="130">
              <template #default="{ row }">{{ row.source_name || '-' }}</template>
            </el-table-column>
            <el-table-column label="新闻标题" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                <el-link v-if="row.url" type="primary" :href="row.url" target="_blank">{{ row.title }}</el-link>
                <template v-else>{{ row.title }}</template>
              </template>
            </el-table-column>
            <el-table-column label="涉及摘要" min-width="200" show-overflow-tooltip>
              <template #default="{ row }"><span class="muted">{{ row.summary }}</span></template>
            </el-table-column>
            <el-table-column label="事件时间" width="100">
              <template #default="{ row }">{{ row.event_time || '-' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="70" align="center">
              <template #default="{ row }">
                <el-button link type="danger" size="small" @click="deleteNews(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无动态信息，点击采集（按姓名匹配官网/媒体新闻）" :image-size="60" />
        </template>
      </div>
      <template #footer><el-button @click="detailVisible = false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Download, Lightning } from '@element-plus/icons-vue'
import PageTable from '../components/PageTable.vue'
import FilterBar from '../components/FilterBar.vue'
import DetailGrid from '../components/DetailGrid.vue'
import { get, getList, post, put, del, fmtDate, exportCsv, ROLE_OPTIONS } from '../api'
import { useDictStore } from '../stores/app'

const dict = useDictStore()
const contacts = ref([])
const loading = ref(false)
const filter = reactive({ q: '', customer: '', role: '' })
const draft = reactive({ q: '', customer: '', role: '' })

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

async function viewDetail(id) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = await get(`/contacts/${id}`)
  detailLoading.value = false
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

async function doExport() {
  const err = await exportCsv('contacts', filteredList.value)
  err ? ElMessage.error(err) : ElMessage.success(`已导出 ${filteredList.value.length} 条`)
}

onMounted(async () => {
  await Promise.all([load(), dict.loadCustomers()])
})
</script>

<style scoped>
.w-full { width: 100%; }
.w-140 { width: 140px; }
.w-180 { width: 180px; }
.w-200 { width: 200px; }

.is-important { color: var(--el-color-warning); font-weight: 500; }
.detail-body { min-height: 80px; }
.notes-alert { margin-top: 12px; }
.tab-actions { margin-bottom: 12px; }
</style>
