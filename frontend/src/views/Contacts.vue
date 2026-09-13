<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">联系人管理</h2>
      <div class="page-toolbar">
        <el-button @click="doExport"><el-icon><Download /></el-icon>&nbsp;导出</el-button>
        <el-button type="primary" @click="openForm()"><el-icon><Plus /></el-icon>&nbsp;新增联系人</el-button>
      </div>
    </div>

    <FilterBar @search="applyFilter" @reset="resetFilter">
      <el-form-item label="姓名/职位">
        <el-input v-model="draft.q" placeholder="搜索姓名或职位..." clearable style="width:200px" />
      </el-form-item>
      <el-form-item label="所属客户">
        <el-select v-model="draft.customer" clearable filterable style="width:180px" @change="applyFilter">
          <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
        </el-select>
      </el-form-item>
      <el-form-item label="角色">
        <el-select v-model="draft.role" clearable style="width:140px" @change="applyFilter">
          <el-option v-for="r in ROLE_OPTIONS" :key="r" :value="r" :label="r" />
        </el-select>
      </el-form-item>
    </FilterBar>

    <el-card shadow="never" body-style="padding:0">
      <PageTable storage-key="contact" :data="filteredList" :loading="loading" :default-sort="{ prop: 'name', order: 'ascending' }">
        <el-table-column prop="name" label="姓名" min-width="110" sortable="custom" class-name="cell-strong">
          <template #default="{ row }">{{ row.name }}</template>
        </el-table-column>
        <el-table-column prop="title" label="职位" min-width="130" sortable="custom" />
        <el-table-column prop="customer_name" label="所属客户" min-width="180" sortable="custom" show-overflow-tooltip />
        <el-table-column prop="phone" label="电话" width="140" sortable="custom" />
        <el-table-column prop="wechat" label="微信" width="120" />
        <el-table-column prop="role" label="角色" width="110" sortable="custom" />
        <el-table-column prop="importance" label="重要性" width="100" sortable="custom" />
        <el-table-column label="操作" width="170" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewDetail(row.id)">查看</el-button>
            <el-button link type="primary" size="small" @click="openForm(row.id)">编辑</el-button>
            <el-button link type="danger" size="small" @click="deleteContact(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </PageTable>
    </el-card>

    <!-- 新增/编辑联系人 -->
    <el-dialog v-model="formVisible" :title="editId ? '编辑联系人' : '新增联系人'" width="600px" destroy-on-close>
      <el-form :model="form" label-width="100px">
        <el-row :gutter="12">
          <el-col :span="12"><el-form-item label="姓名" required><el-input v-model="form.name" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="职位"><el-input v-model="form.title" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12"><el-form-item label="电话"><el-input v-model="form.phone" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="角色">
              <el-select v-model="form.role" clearable style="width:100%">
                <el-option v-for="r in ROLE_OPTIONS" :key="r" :value="r" :label="r" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属客户">
              <el-select v-model="form.customer_id" clearable filterable style="width:100%">
                <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="标签"><el-input v-model="form.tags" placeholder="逗号分隔，如: 高层,关键决策" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.notes" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" @click="saveForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 联系人详情 + 动态 -->
    <el-dialog v-model="detailVisible" :title="detail?.name || '联系人详情'" width="760px" destroy-on-close>
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
        <div v-if="detail.notes" class="muted" style="margin-top:12px">备注：{{ detail.notes }}</div>
        <div style="display:flex;align-items:center;gap:8px;margin:16px 0 8px">
          <span style="font-weight:600;font-size:13px">动态信息（官网/媒体提及）</span>
          <el-button type="primary" size="small" :loading="newsLoading" @click="collectNews">
            <el-icon><Lightning /></el-icon>&nbsp;采集
          </el-button>
        </div>
        <template v-if="(detail.contact_news || []).length">
          <el-table :data="detail.contact_news" size="small">
            <el-table-column label="采集时间" width="100"><template #default="{ row }">{{ fmtDate(row.crawled_at) || '-' }}</template></el-table-column>
            <el-table-column label="来源" width="130"><template #default="{ row }">{{ row.source_name || '-' }}</template></el-table-column>
            <el-table-column label="新闻标题" min-width="180">
              <template #default="{ row }">
                <a v-if="row.url" :href="row.url" target="_blank" style="color:var(--el-color-primary)">{{ row.title }}</a>
                <template v-else>{{ row.title }}</template>
              </template>
            </el-table-column>
            <el-table-column label="涉及摘要" min-width="200"><template #default="{ row }"><span class="muted">{{ row.summary }}</span></template></el-table-column>
            <el-table-column label="事件时间" width="100"><template #default="{ row }">{{ row.event_time || '-' }}</template></el-table-column>
            <el-table-column label="操作" width="60" align="center">
              <template #default="{ row }">
                <el-button link type="danger" size="small" @click="deleteNews(row.id)"><el-icon><Delete /></el-icon></el-button>
              </template>
            </el-table-column>
          </el-table>
        </template>
        <el-empty v-else description="暂无动态信息，点击采集（按姓名匹配官网/媒体新闻）" :image-size="60" />
      </template>
      <template #footer><el-button @click="detailVisible = false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Download, Lightning, Delete } from '@element-plus/icons-vue'
import PageTable from '../components/PageTable.vue'
import FilterBar from '../components/FilterBar.vue'
import DetailGrid from '../components/DetailGrid.vue'
import { get, post, put, del, fmtDate, exportCsv } from '../api'
import { useDictStore, } from '../stores/app'
import { ROLE_OPTIONS } from '../api'

const dict = useDictStore()
const contacts = ref([])
const loading = ref(false)
const filter = reactive({ q: '', customer: '', role: '' })
const draft = reactive({ q: '', customer: '', role: '' })
const filteredList = computed(() => contacts.value.filter((ct) => {
  if (filter.q && !ct.name.toLowerCase().includes(filter.q.toLowerCase()) && !(ct.title || '').toLowerCase().includes(filter.q.toLowerCase())) return false
  if (filter.customer && String(ct.customer_id) !== String(filter.customer)) return false
  if (filter.role && ct.role !== filter.role) return false
  return true
}))

async function load() {
  loading.value = true
  contacts.value = (await get('/contacts')) || []
  loading.value = false
}
function applyFilter() { Object.assign(filter, draft) }
function resetFilter() {
  Object.assign(draft, { q: '', customer: '', role: '' })
  Object.assign(filter, draft)
}

// ---- 新增/编辑 ----
const formVisible = ref(false)
const editId = ref(null)
const form = reactive({})
function openForm(id) {
  editId.value = id || null
  Object.keys(form).forEach((k) => delete form[k])
  Object.assign(form, { name: '', title: '', phone: '', email: '', wechat: '', role: '', tags: '', customer_id: null, importance: '', notes: '' })
  if (id) get(`/contacts/${id}`).then((ct) => { Object.keys(form).forEach((k) => (form[k] = ct[k] ?? form[k])) })
  formVisible.value = true
}
async function saveForm() {
  if (!form.name) return ElMessage.error('请输入姓名')
  const r = editId.value ? await put(`/contacts/${editId.value}`, form) : await post('/contacts', form)
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success('保存成功')
  formVisible.value = false
  load(); dict.loadContacts()
}
async function deleteContact(id) {
  await ElMessageBox.confirm('确认删除该联系人？', '删除联系人')
  const r = await del(`/contacts/${id}`)
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success('已删除'); load(); dict.loadContacts()
}

// ---- 详情 + 动态 ----
const detailVisible = ref(false)
const detail = ref(null)
const newsLoading = ref(false)
async function viewDetail(id) {
  detail.value = await get(`/contacts/${id}`)
  detailVisible.value = true
}
async function collectNews() {
  newsLoading.value = true
  const r = await post(`/contacts/${detail.value.id}/collect-news`)
  newsLoading.value = false
  ElMessage(r.message || r.error || '完成')
  detail.value = await get(`/contacts/${detail.value.id}`)
}
async function deleteNews(id) {
  await ElMessageBox.confirm('确认删除该条动态？', '删除动态')
  await del(`/news/contact/${id}`)
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
