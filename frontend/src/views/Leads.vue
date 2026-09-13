<template>
  <div class="page">
    <div class="page-header">
      <el-tabs v-model="tab" class="flex-1">
        <el-tab-pane name="active"><template #label>待转化 ({{ counts.active }})</template></el-tab-pane>
        <el-tab-pane name="pool"><template #label>公海池 ({{ counts.pool }})</template></el-tab-pane>
        <el-tab-pane name="converted"><template #label>已转化 ({{ counts.converted }})</template></el-tab-pane>
        <el-tab-pane name="abandoned"><template #label>已删除 ({{ counts.abandoned }})</template></el-tab-pane>
      </el-tabs>
      <div class="page-toolbar">
        <el-button type="primary" @click="openForm()"><el-icon><Plus /></el-icon>&nbsp;手工新增</el-button>
        <el-button type="primary" plain @click="doCrawl"><el-icon><Refresh /></el-icon>&nbsp;采集线索</el-button>
        <el-button @click="doExport"><el-icon><Download /></el-icon>&nbsp;导出</el-button>
      </div>
    </div>

    <el-alert v-if="crawl.running" type="info" :closable="false" class="card-block"
      :title="`采集进行中：${crawl.phase} ${crawl.progress}/${crawl.total || '-'} ${crawl.current} 已生成 ${crawl.count} 条线索`" />

    <FilterBar @search="applyFilter" @reset="resetFilter">
      <el-form-item label="名称">
        <el-input v-model="draft.q" placeholder="搜索线索标题..." clearable style="width:200px" />
      </el-form-item>
      <el-form-item label="地区">
        <el-input v-model="draft.region" placeholder="如: 浙江" clearable style="width:140px" />
      </el-form-item>
      <el-form-item label="创建时间从">
        <el-date-picker v-model="draft.from" type="date" value-format="YYYY-MM-DD" style="width:150px" />
      </el-form-item>
      <el-form-item label="至">
        <el-date-picker v-model="draft.to" type="date" value-format="YYYY-MM-DD" style="width:150px" />
      </el-form-item>
    </FilterBar>

    <el-card shadow="never" body-style="padding:0">
      <PageTable storage-key="leads" :data="filteredList" :loading="loading" :default-sort="{ prop: 'created_at', order: 'descending' }">
        <el-table-column prop="serial_no" label="流水号" width="88" sortable="custom">
          <template #default="{ row }">
            <span class="mono muted" style="font-size:12px">{{ row.serial_no || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="240" sortable="custom" class-name="cell-strong">
          <template #default="{ row }">
            <div>
              {{ row.title }}
              <el-tag size="small" :type="isCrawled(row) ? 'primary' : 'info'" effect="plain">{{ isCrawled(row) ? '采集' : '手工' }}</el-tag>
            </div>
            <div v-if="row.contact_name" class="cell-sub">{{ row.purchaser }} | 联系人: {{ row.contact_name }} {{ row.contact_phone }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="bid_type" label="类别" width="150" sortable="custom">
          <template #default="{ row }">
            <el-tag size="small" :type="bidTagType(row.bid_type)">{{ row.bid_type || '待分类' }}</el-tag>
            <el-tooltip v-if="relCount(row)" :content="`关联${relCount(row)}个客户`">
              <el-tag size="small" type="success" effect="plain" style="margin-left:4px">+{{ relCount(row) }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="budget" label="预算(万)" width="100" sortable="custom" align="right" />
        <el-table-column prop="region" label="地区" width="130" sortable="custom" show-overflow-tooltip />
        <el-table-column prop="deadline" label="截止" width="110" sortable="custom" />
        <el-table-column prop="created_at" label="创建" width="110" sortable="custom" />
        <el-table-column prop="source_platform" label="来源" width="140" show-overflow-tooltip />
        <el-table-column v-if="tab === 'pool' || tab === 'abandoned'" prop="reason" label="原因" width="150" show-overflow-tooltip>
          <template #default="{ row }"><span class="muted">{{ row.reason || '-' }}</span></template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90" sortable="custom">
          <template #default="{ row }">
            <el-tag size="small" :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="230" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewDetail(row.id)">查看</el-button>
            <template v-if="row.status === 'active'">
              <el-button link type="success" size="small" @click="openConvert(row.id)">转化</el-button>
              <el-button link size="small" @click="releaseLead(row.id)">释放</el-button>
              <el-button link type="danger" size="small" @click="deleteLead(row.id)">删除</el-button>
            </template>
            <template v-else-if="row.status === 'pool'">
              <el-button link type="success" size="small" @click="claimLead(row.id)">领取</el-button>
            </template>
            <template v-else-if="row.status === 'abandoned'">
              <el-button link type="primary" size="small" @click="openForm(row.id)">编辑</el-button>
              <el-button link type="success" size="small" @click="restoreLead(row.id)">恢复</el-button>
            </template>
          </template>
        </el-table-column>
      </PageTable>
    </el-card>

    <!-- 新建/编辑线索 -->
    <el-dialog v-model="formVisible" :title="editId ? '编辑线索' : '新建线索'" width="640px" destroy-on-close>
      <el-form :model="form" label-width="110px">
        <el-form-item label="标题" required><el-input v-model="form.title" /></el-form-item>
        <el-row :gutter="12">
          <el-col :span="12"><el-form-item label="预算(万)"><el-input v-model="form.budget" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="截止日期"><el-date-picker v-model="form.deadline" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12"><el-form-item label="地区"><el-input v-model="form.region" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="采购方"><el-input v-model="form.purchaser" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8"><el-form-item label="联系人"><el-input v-model="form.contact_name" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="联系方式"><el-input v-model="form.contact_phone" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="地址"><el-input v-model="form.address" /></el-form-item></el-col>
        </el-row>
        <el-form-item label="来源平台"><el-input v-model="form.source_platform" placeholder="手动录入" /></el-form-item>
        <el-form-item label="来源URL"><el-input v-model="form.source_url" placeholder="采集线索自动带来源链接" /></el-form-item>
        <el-form-item label="服务内容"><el-input v-model="form.service_content" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" @click="saveForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 转化线索 -->
    <el-dialog v-model="convertVisible" title="转化线索为商机" width="680px" destroy-on-close>
      <el-form :model="cv" label-width="110px">
        <el-form-item label="商机名称" required><el-input v-model="cv.title" /></el-form-item>
        <template v-if="cvIsWin">
          <el-alert type="warning" :closable="false" style="margin-bottom:12px">
            此线索为中标/成交公告，中标单位「{{ cvWinnerText || '—' }}」，采购单位「{{ cvPurchaserText || '—' }}」
          </el-alert>
          <el-form-item label="中标单位">
            <el-select v-model="cv.winnerIds" multiple filterable style="width:100%" placeholder="从客户库选择（可多选，作为合作目标）">
              <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
            </el-select>
          </el-form-item>
          <el-form-item label="新中标单位">
            <el-input v-model="cv.winnerNew" :placeholder="cv.winnerIds.length ? '多家用逗号分隔，已勾选客户无需重复输入' : (cvWinnerText || '输入新中标单位名称')" />
          </el-form-item>
          <el-form-item label="采购单位">
            <el-select v-model="cv.purchaserId" filterable clearable style="width:100%" placeholder="从客户库选择（客户方）">
              <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
            </el-select>
          </el-form-item>
          <el-form-item label="新采购单位">
            <el-input v-model="cv.purchaserNew" :placeholder="cv.purchaserId ? '已勾选客户无需重复输入' : (cvPurchaserText || '输入新采购单位名称')" />
          </el-form-item>
          <div class="muted" style="margin:0 0 10px 110px">中标单位将优先作为商机客户；如未选择自动创建新客户。</div>
        </template>
        <template v-else>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="选择客户">
                <el-select v-model="cv.customerId" filterable clearable style="width:100%" placeholder="从客户库选择">
                  <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="选择联系人">
                <el-select v-model="cv.contactId" filterable clearable style="width:100%" placeholder="从联系人库选择">
                  <el-option v-for="c in dict.contacts" :key="c.id" :value="c.id" :label="c.name" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <div class="muted" style="margin:0 0 10px 110px">未选择时自动创建：客户取线索采购方，联系人/电话取线索提取的信息。</div>
          <el-form-item label="新客户名称">
            <el-input v-model="cv.newCustomer" :placeholder="lead?.purchaser || '输入新客户名称（已选择客户则留空）'" />
          </el-form-item>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="新联系人">
                <el-input v-model="cv.newContact" :placeholder="lead?.contact_name || '输入新联系人姓名'" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="联系电话">
                <el-input v-model="cv.newPhone" :placeholder="lead?.contact_phone || '输入联系电话'" />
              </el-form-item>
            </el-col>
          </el-row>
        </template>
        <el-form-item label="转化原因">
          <el-input v-model="cv.reason" type="textarea" :rows="3"
            placeholder="填写转化原因/商机背景，将作为该商机的第一条联络记录（如：中标公告转入，需尽快对接合同签订）" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12"><el-form-item label="金额(万)"><el-input v-model="cv.amount" type="number" /></el-form-item></el-col>
          <el-col :span="12">
            <el-form-item label="阶段">
              <el-select v-model="cv.stage" style="width:100%">
                <el-option v-for="s in dict.stageNames" :key="s" :value="s" :label="s" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="convertVisible = false">取消</el-button>
        <el-button type="primary" @click="saveConvert">确认转化</el-button>
      </template>
    </el-dialog>

    <!-- 线索详情 -->
    <el-dialog v-model="detailVisible" title="线索详情" width="680px" destroy-on-close>
      <template v-if="detail">
        <DetailGrid :items="[
          { label: '流水号', slot: 'serial', full: false },
          { label: '标题', value: detail.title, full: true },
          { label: '类别', slot: 'bid' },
          { label: '预算', value: detail.budget ? detail.budget + '万' : '-' },
          { label: '截止', value: fmtDate(detail.deadline) || '-' },
          { label: '地区', value: detail.region },
          { label: '客户方', value: detail.purchaser },
          { label: '中标单位', value: detail.winner },
          { label: '联系人', value: detail.contact_name },
          { label: '联系方式', value: detail.contact_phone },
          { label: '地址', value: detail.address },
          { label: '来源', value: detail.source_platform },
          { label: '匹配度', value: `${detail.match_score || 0}% (${detail.match_level || ''})` },
          { label: '状态', value: statusLabel(detail.status) },
        ]">
          <template #serial>
            <span class="mono" style="font-weight:600;color:#1f2d24">{{ detail.serial_no || '-' }}</span>
          </template>
          <template #bid>
            <el-tag size="small" :type="bidTagType(detail.bid_type)">{{ detail.bid_type || '待分类' }}</el-tag>
          </template>
        </DetailGrid>
        <div v-if="detail.match_reason" class="muted" style="margin-top:12px">匹配原因: {{ detail.match_reason }}</div>
        <div v-if="detail.service_content" class="muted" style="margin-top:8px">服务内容：{{ detail.service_content }}</div>
        <div v-if="detail.source_url" class="break-all"
          style="margin-top:12px;font-size:13px;padding:8px 12px;background:#f8fafc;border-radius:6px;display:flex;align-items:flex-start;gap:8px">
          <div style="flex:1">
            <span class="muted">原文链接：</span>
            <a :href="detail.source_url" target="_blank" style="color:var(--el-color-primary)">{{ detail.source_url }}</a>
          </div>
          <el-button type="primary" size="small" :loading="fulltextLoading" @click="openFulltext">全文</el-button>
        </div>
      </template>
      <template #footer><el-button @click="detailVisible = false">关闭</el-button></template>
    </el-dialog>

    <!-- 公告全文 -->
    <el-drawer v-model="fulltextVisible" size="55%" title="公告全文">
      <div v-loading="fulltextLoading" style="min-height:200px">
        <el-alert v-if="fulltextError" type="warning" :closable="false" :title="fulltextError" />
        <!-- eslint-disable-next-line vue/no-v-html -->
        <div v-else-if="fulltext" class="md-body" v-html="fulltextHtml"></div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Download } from '@element-plus/icons-vue'
import { marked } from 'marked'
import PageTable from '../components/PageTable.vue'
import FilterBar from '../components/FilterBar.vue'
import DetailGrid from '../components/DetailGrid.vue'
import { get, post, put, fmtDate, exportCsv } from '../api'
import { useDictStore, useCrawlStore } from '../stores/app'

const dict = useDictStore()
const crawl = useCrawlStore()

const leads = ref([])
const loading = ref(false)
const tab = ref('active')
const filter = reactive({ q: '', region: '', from: '', to: '' })
const draft = reactive({ q: '', region: '', from: '', to: '' })

const counts = computed(() => ({
  active: leads.value.filter((l) => l.status === 'active').length,
  pool: leads.value.filter((l) => l.status === 'pool').length,
  converted: leads.value.filter((l) => l.status === 'converted').length,
  abandoned: leads.value.filter((l) => l.status === 'abandoned').length,
}))
const baseList = computed(() => leads.value.filter((l) => l.status === tab.value))
const filteredList = computed(() => baseList.value.filter((l) => {
  if (filter.q && !l.title.toLowerCase().includes(filter.q.toLowerCase()) && !(l.serial_no || '').includes(filter.q)) return false
  if (filter.region && !(l.region || '').includes(filter.region)) return false
  if (filter.from && l.created_at && l.created_at < filter.from) return false
  if (filter.to && l.created_at && l.created_at > filter.to) return false
  return true
}))

const isCrawled = (l) => (l.source_platform && l.source_platform !== '手动录入') || !!l.source_url
const relCount = (l) => (l.related_customer_ids || '').split(',').filter(Boolean).length
const bidTagType = (t) => (/中标|成交/.test(t || '') ? 'success' : t ? 'warning' : 'info')
const statusLabel = (s) => ({ converted: '已转化', abandoned: '已删除', pool: '公海池' }[s] || '待转化')
const statusType = (s) => ({ converted: 'success', abandoned: 'danger', pool: 'warning' }[s] || 'primary')

async function load() {
  loading.value = true
  leads.value = (await get('/leads')) || []
  loading.value = false
}
function applyFilter() { Object.assign(filter, draft) }
function resetFilter() {
  Object.assign(draft, { q: '', region: '', from: '', to: '' })
  Object.assign(filter, draft)
}

async function doCrawl() {
  const msg = await crawl.start()
  if (msg) ElMessage.error(msg)
  else ElMessage.info('采集已启动，正在抓取并AI分析...')
}
watch(() => crawl.finishedAt, () => { load(); dict.loadCustomers() })

// ---- 行操作 ----
async function claimLead(id) {
  const r = await post(`/leads/${id}/claim`, { assignee: '李明' })
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success(r.message || '已领取'); load()
}
async function releaseLead(id) {
  const { value: reason } = await ElMessageBox.prompt('释放原因（将显示在公海池列表）:', '释放至公海', {
    inputPlaceholder: '如：地区不符 / 暂无跟进人力 / 已有同事对接',
    inputValidator: (v) => !!v?.trim() || '请填写释放原因',
  })
  const r = await post(`/leads/${id}/release`, { reason: reason.trim() })
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success(r.message || '已释放至公海池'); load()
}
async function deleteLead(id) {
  const { value: reason } = await ElMessageBox.prompt('删除原因（将显示在已删除列表，可恢复）:', '删除线索', {
    inputPlaceholder: '如：重复线索 / 与业务无关 / 信息有误',
    inputValidator: (v) => !!v?.trim() || '请填写删除原因',
  })
  const r = await post(`/leads/${id}/abandon`, { reason: reason.trim() })
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success(r.message || '已删除'); load()
}
async function restoreLead(id) {
  await ElMessageBox.confirm('确认恢复该线索为待转化？', '恢复线索')
  const r = await put(`/leads/${id}`, { status: 'active' })
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success(r.message || '已恢复'); load()
}

// ---- 新建/编辑 ----
const formVisible = ref(false)
const editId = ref(null)
const form = reactive({})
function openForm(id) {
  editId.value = id || null
  Object.keys(form).forEach((k) => delete form[k])
  Object.assign(form, {
    title: '', budget: '', deadline: '', region: '', purchaser: '', contact_name: '',
    contact_phone: '', address: '', source_platform: '手动录入', source_url: '', service_content: '',
  })
  if (id) {
    get(`/leads/${id}`).then((l) => { Object.keys(form).forEach((k) => (form[k] = l[k] ?? form[k])) })
  }
  formVisible.value = true
}
async function saveForm() {
  if (!form.title) return ElMessage.error('请输入标题')
  const r = editId.value
    ? await put(`/leads/${editId.value}`, form)
    : await post('/leads', form)
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success(editId.value ? '更新成功' : '创建成功')
  formVisible.value = false
  load()
}

// ---- 详情 ----
const detailVisible = ref(false)
const detail = ref(null)
async function viewDetail(id) {
  detail.value = await get(`/leads/${id}`)
  detailVisible.value = true
}

// ---- 全文 ----
const fulltextVisible = ref(false)
const fulltextLoading = ref(false)
const fulltext = ref('')
const fulltextError = ref('')
const fulltextHtml = computed(() => marked.parse(fulltext.value || ''))
async function openFulltext() {
  fulltextVisible.value = true
  fulltextLoading.value = true
  fulltext.value = ''
  fulltextError.value = ''
  const r = await get(`/leads/${detail.value.id}/fulltext`)
  fulltextLoading.value = false
  if (r.error) { fulltextError.value = r.error; return }
  fulltext.value = r.text || '（无正文内容）'
}

// ---- 转化 ----
const convertVisible = ref(false)
const cv = reactive({ title: '', winnerIds: [], winnerNew: '', purchaserId: null, purchaserNew: '', customerId: null, contactId: null, newCustomer: '', newContact: '', newPhone: '', amount: '', stage: '', reason: '' })
const cvConvertId = ref(null)
const lead = ref({})
const cvIsWin = computed(() => /中标|成交/.test(lead.value.bid_type || ''))
const cvWinnerText = computed(() => lead.value.winner || '')
const cvPurchaserText = computed(() => lead.value.purchaser || '')
async function openConvert(id) {
  await Promise.all([dict.loadCustomers(), dict.loadContacts(), dict.loadStages()])
  lead.value = await get(`/leads/${id}`)
  cvConvertId.value = id
  Object.assign(cv, {
    title: lead.value.title, winnerIds: [], winnerNew: '', purchaserId: null, purchaserNew: '',
    customerId: null, contactId: null, newCustomer: '', newContact: '', newPhone: '',
    amount: '', stage: dict.stageNames[0] || '', reason: '',
  })
  const customers = dict.customers
  const winnerText = cvWinnerText.value, purchaserText = cvPurchaserText.value
  if (cvIsWin.value) {
    cv.winnerIds = winnerText ? customers.filter((c) => winnerText.includes(c.name) || c.name.includes(winnerText)).map((c) => c.id) : []
    cv.winnerNew = cv.winnerIds.length ? '' : winnerText
    const purMatches = purchaserText ? customers.filter((c) => purchaserText.includes(c.name) || c.name.includes(purchaserText)).map((c) => c.id) : []
    cv.purchaserId = purMatches[0] || null
    cv.purchaserNew = cv.purchaserId ? '' : purchaserText
  } else {
    cv.newCustomer = purchaserText
    cv.newContact = lead.value.contact_name || ''
    cv.newPhone = lead.value.contact_phone || ''
  }
  convertVisible.value = true
}
async function saveConvert() {
  const id = cvConvertId.value
  const d = {
    title: cv.title,
    contact_id: cv.contactId || null,
    contact_name: cv.newContact || '', contact_phone: cv.newPhone || '',
    amount: cv.amount, stage: cv.stage, reason: cv.reason.trim(),
  }
  if (cvIsWin.value) {
    const selNames = cv.winnerIds.map((i) => (dict.customers.find((c) => c.id === i) || {}).name).filter(Boolean)
    const typed = (cv.winnerNew || '').split(/[,，]/).map((s) => s.trim()).filter(Boolean)
    const winnerNew = [...new Set([...selNames, ...typed])]
    const purSelName = cv.purchaserId ? (dict.customers.find((c) => c.id === cv.purchaserId) || {}).name : ''
    const purTyped = (cv.purchaserNew || '').split(/[,，]/).map((s) => s.trim()).filter(Boolean)
    const purchaserNew = [...new Set([...(purSelName ? [purSelName] : []), ...purTyped])]
    d.winner_customer_names = winnerNew
    d.purchaser_customer_names = purchaserNew
    if ([...winnerNew, ...purchaserNew].length > 0) d.customer_name = [...winnerNew, ...purchaserNew][0]
  } else {
    d.customer_id = cv.customerId || null
    d.customer_name = cv.newCustomer || ''
    if (d.customer_id && d.customer_name) d.customer_name = ''
  }
  if (!d.title) return ElMessage.error('请输入商机名称')
  const r = await post(`/leads/${id}/convert`, d)
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success(r.message || '已转化')
  convertVisible.value = false
  tab.value = 'converted'
  load()
}

// ---- 导出 ----
async function doExport() {
  const err = await exportCsv('leads', filteredList.value)
  err ? ElMessage.error(err) : ElMessage.success(`已导出 ${filteredList.value.length} 条`)
}

onMounted(async () => {
  await Promise.all([load(), dict.loadCustomers()])
  crawl.checkRunning()
})
</script>

<style scoped>
.flex-1 { flex: 1; }
.flex-1 :deep(.el-tabs__header) { margin-bottom: 0; }
</style>
