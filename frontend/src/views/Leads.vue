<template>
  <div class="page">
    <!-- 顶部：标题 + 状态分段切换 + 主操作 -->
    <PageHeader title="线索管理" subtitle="采集公告、匹配评估与转化 pipeline">
      <template #actions>
        <el-button :icon="Download" plain @click="doExport">导出</el-button>
        <el-button :icon="Refresh" plain @click="doCrawl">采集线索</el-button>
        <el-button type="primary" :icon="Plus" @click="openForm()">手工新增</el-button>
      </template>
    </PageHeader>

    <!-- 状态分段（Segmented） -->
    <div class="tabs-bar">
      <div class="seg-group" role="tablist">
        <button
          v-for="t in TABS" :key="t.key"
          class="seg-btn" :class="{ 'is-active': tab === t.key }"
          role="tab" @click="tab = t.key"
        >
          <span class="seg-label">{{ t.label }}</span>
          <span class="seg-count">{{ counts[t.key] || 0 }}</span>
        </button>
      </div>
      <div class="tabs-hint muted" v-if="filteredList.length !== counts[tab]">
        筛选中：{{ filteredList.length }} / {{ counts[tab] || 0 }}
      </div>
    </div>

    <el-alert v-if="crawl.running" type="info" :closable="false" class="crawl-alert">
      <div class="crawl-line">
        <el-icon class="is-loading" :size="14"><Loading /></el-icon>
        <span>{{ crawl.phase }} · {{ crawl.progress }}/{{ crawl.total || '—' }}</span>
        <span class="muted" v-if="crawl.current">· {{ crawl.current }}</span>
        <span class="crawl-count">已生成 <b>{{ crawl.count }}</b> 条</span>
      </div>
    </el-alert>

    <!-- 搜索 -->
    <FilterBar @search="applyFilter" @reset="resetFilter">
      <el-form-item label="关键词">
        <el-input v-model="draft.q" placeholder="标题 / 编号 / 公告全文" clearable style="width:240px" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="draft.status" clearable placeholder="全部状态" style="width:140px">
          <el-option value="active" label="待转化" />
          <el-option value="pool" label="公海池" />
          <el-option value="converted" label="已转化" />
          <el-option value="abandoned" label="已删除" />
        </el-select>
      </el-form-item>
      <el-form-item label="地区">
        <el-input v-model="draft.region" placeholder="如: 浙江" clearable style="width:150px" />
      </el-form-item>
      <el-form-item label="创建从">
        <el-date-picker v-model="draft.from" type="date" value-format="YYYY-MM-DD" placeholder="起始" style="width:150px" />
      </el-form-item>
      <el-form-item label="创建至">
        <el-date-picker v-model="draft.to" type="date" value-format="YYYY-MM-DD" placeholder="结束" style="width:150px" />
      </el-form-item>
    </FilterBar>

    <!-- 表格 -->
    <div class="table-wrap">
      <PageTable
        storage-key="leads"
        :data="filteredList"
        :loading="loading"
        :default-sort="{ prop: 'created_at', order: 'descending' }"
        :empty-text="emptyTextForTab"
        :empty-hint="emptyHintForTab"
      >
        <template #empty-action>
          <el-button
            v-if="tab === 'all' && !filter.q && !filter.region && !filter.status"
            type="primary" plain size="small" :icon="Refresh" @click="doCrawl" style="margin-top:12px"
          >立即采集公告</el-button>
        </template>

        <el-table-column prop="serial_no" label="编号" width="94" sortable="custom">
          <template #default="{ row }">
            <span class="mono serial">{{ row.serial_no || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="260" sortable="custom">
          <template #default="{ row }">
            <span class="cell-title-text is-link" :title="row.title" @click="viewDetail(row.id)">{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="bid_type" label="类别" width="140" sortable="custom">
          <template #default="{ row }">
            <el-tag size="small" :type="bidTagType(row.bid_type)" effect="plain" round>
              {{ bidShort(row.bid_type) }}
            </el-tag>
            <el-tooltip v-if="relCount(row)" :content="`关联 ${relCount(row)} 个客户`">
              <el-tag size="small" type="success" effect="plain" round class="rel-tag">+{{ relCount(row) }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="budget" label="预算(万)" width="106" sortable="custom" align="right">
          <template #default="{ row }">
            <span v-if="row.budget" class="mono budget">{{ fmtBudgetNum(row.budget) }}</span>
            <span v-else class="mono dim">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="region" label="地区" width="140" sortable="custom" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="region-text">{{ row.region || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="deadline" label="截止" width="112" sortable="custom">
          <template #default="{ row }">
            <span v-if="row.deadline" class="mono date" :class="{ 'is-urgent': row.days_left !== null && row.days_left <= 7 }">
              {{ fmtDateMDY(row.deadline) }}
            </span>
            <span v-else class="mono dim">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建" width="106" sortable="custom">
          <template #default="{ row }">
            <span class="mono date muted">{{ fmtDateMDY(row.created_at) || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="source_platform" label="来源" width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="dim">{{ row.source_platform || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="tab === 'pool' || tab === 'abandoned'" prop="reason" label="原因" width="170" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="muted reason-cell">{{ row.reason || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="92" sortable="custom">
          <template #default="{ row }">
            <span class="status-pill" :class="`status-pill--${row.status}`">
              <i class="status-indicator"></i>
              {{ statusLabel(row.status) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right" align="right">
          <template #default="{ row }">
            <div class="row-actions">
              <template v-if="row.status === 'active'">
                <el-button link type="success" size="small" @click="openConvert(row.id)">转化</el-button>
                <el-button link size="small" @click="releaseLead(row.id)">释放</el-button>
                <el-button link type="danger" size="small" @click="deleteLead(row.id)">删除</el-button>
              </template>
              <template v-else-if="row.status === 'pool'">
                <el-button link type="success" size="small" @click="claimLead(row.id)">领取</el-button>
              </template>
              <template v-else-if="row.status === 'abandoned'">
                <el-button link size="small" @click="openForm(row.id)">编辑</el-button>
                <el-button link type="success" size="small" @click="restoreLead(row.id)">恢复</el-button>
              </template>
            </div>
          </template>
        </el-table-column>
      </PageTable>
    </div>

    <!-- 新建/编辑线索 -->
    <el-dialog v-model="formVisible" :title="editId ? '编辑线索' : '手工新增线索'" width="720px" destroy-on-close class="form-dialog">
      <el-form :model="form" label-width="98px" label-position="right">
        <div class="form-section">
          <div class="section-title">基本信息</div>
          <el-form-item label="标题" required>
            <el-input v-model="form.title" placeholder="一句话概括，如：四川省林业厅无人机森林病虫害防治服务" maxlength="200" show-word-limit />
          </el-form-item>
          <el-row :gutter="12">
            <el-col :span="8"><el-form-item label="预算(万)"><el-input v-model="form.budget" placeholder="如 150 或 1,200万元" /></el-form-item></el-col>
            <el-col :span="8"><el-form-item label="截止日期"><el-date-picker v-model="form.deadline" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
            <el-col :span="8"><el-form-item label="地区"><el-input v-model="form.region" placeholder="如：四川成都" /></el-form-item></el-col>
          </el-row>
          <el-form-item label="采购方"><el-input v-model="form.purchaser" placeholder="采购单位 / 招标人" /></el-form-item>
          <el-form-item label="服务内容">
            <el-input v-model="form.service_content" type="textarea" :rows="2" placeholder="无人机巡飞、病虫害防治、航拍测绘…" />
          </el-form-item>
        </div>

        <div class="form-section">
          <div class="section-title">联系人</div>
          <el-row :gutter="12">
            <el-col :span="8"><el-form-item label="姓名"><el-input v-model="form.contact_name" /></el-form-item></el-col>
            <el-col :span="8"><el-form-item label="电话"><el-input v-model="form.contact_phone" /></el-form-item></el-col>
            <el-col :span="8"><el-form-item label="地址"><el-input v-model="form.address" /></el-form-item></el-col>
          </el-row>
        </div>

        <div class="form-section">
          <div class="section-title">来源</div>
          <el-row :gutter="12">
            <el-col :span="8"><el-form-item label="平台"><el-input v-model="form.source_platform" placeholder="手动录入" /></el-form-item></el-col>
            <el-col :span="16"><el-form-item label="原文链接"><el-input v-model="form.source_url" placeholder="https://（采集线索自动带上）" /></el-form-item></el-col>
          </el-row>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" @click="saveForm">{{ editId ? '保存修改' : '创建线索' }}</el-button>
      </template>
    </el-dialog>

    <!-- 转化线索 -->
    <el-dialog v-model="convertVisible" title="转化为商机" width="720px" destroy-on-close class="form-dialog">
      <el-form :model="cv" label-width="98px">
        <div class="form-section">
          <div class="section-title">商机</div>
          <el-form-item label="商机名称" required><el-input v-model="cv.title" /></el-form-item>
          <el-row :gutter="12">
            <el-col :span="12"><el-form-item label="金额(万)"><el-input v-model="cv.amount" type="number" placeholder="留空则取线索预算" /></el-form-item></el-col>
            <el-col :span="12">
              <el-form-item label="初始阶段">
                <el-select v-model="cv.stage" style="width:100%">
                  <el-option v-for="s in dict.stageNames" :key="s" :value="s" :label="s" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <template v-if="cvIsWin">
          <div class="form-section">
            <div class="section-title">客户归属</div>
            <el-alert type="warning" :closable="false" class="conv-alert">
              中标 / 成交公告：中标单位「{{ cvWinnerText || '—' }}」；采购单位「{{ cvPurchaserText || '—' }}」
            </el-alert>
            <el-form-item label="中标单位">
              <el-select v-model="cv.winnerIds" multiple filterable style="width:100%" placeholder="从客户库选择（可多选，作为合作目标）">
                <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
              </el-select>
            </el-form-item>
            <el-form-item label="新中标单位">
              <el-input v-model="cv.winnerNew" :placeholder="cv.winnerIds.length ? '多家用逗号分隔；已勾选的无需重复输入' : (cvWinnerText || '输入新中标单位名称')" />
            </el-form-item>
            <el-form-item label="采购单位">
              <el-select v-model="cv.purchaserId" filterable clearable style="width:100%" placeholder="从客户库选择（客户方）">
                <el-option v-for="c in dict.customers" :key="c.id" :value="c.id" :label="c.name" />
              </el-select>
            </el-form-item>
            <el-form-item label="新采购单位">
              <el-input v-model="cv.purchaserNew" :placeholder="cv.purchaserId ? '已勾选客户无需重复输入' : (cvPurchaserText || '输入新采购单位名称')" />
            </el-form-item>
            <div class="field-hint">中标单位将优先作为商机客户；若未选择则自动创建新客户。</div>
          </div>
        </template>
        <template v-else>
          <div class="form-section">
            <div class="section-title">客户归属</div>
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
            <el-form-item label="新客户名称">
              <el-input v-model="cv.newCustomer" :placeholder="lead?.purchaser || '未选择客户则自动新建，可留空'" />
            </el-form-item>
            <el-row :gutter="12">
              <el-col :span="12"><el-form-item label="新联系人"><el-input v-model="cv.newContact" :placeholder="lead?.contact_name || '姓名'" /></el-form-item></el-col>
              <el-col :span="12"><el-form-item label="联系电话"><el-input v-model="cv.newPhone" :placeholder="lead?.contact_phone || '手机 / 座机'" /></el-form-item></el-col>
            </el-row>
          </div>
        </template>

        <div class="form-section">
          <div class="section-title">转化说明</div>
          <el-form-item label="备注">
            <el-input v-model="cv.reason" type="textarea" :rows="3"
              placeholder="填写转化原因 / 商机背景，将作为该商机的第一条联络记录（如：中标公告转入，尽快对接合同签订）" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="convertVisible = false">取消</el-button>
        <el-button type="primary" @click="saveConvert">确认转化</el-button>
      </template>
    </el-dialog>

    <!-- 线索详情 -->
    <el-dialog v-model="detailVisible" title="线索详情" width="780px" destroy-on-close class="detail-dialog">
      <template v-if="detail">
        <!-- 头部：标题 + 关键 tag + 状态 -->
        <div class="detail-hero">
          <div class="detail-hero-body">
            <div class="detail-hero-title">{{ detail.title }}</div>
            <div class="detail-hero-meta">
              <span class="mono serial">{{ detail.serial_no || '—' }}</span>
              <el-tag size="small" :type="bidTagType(detail.bid_type)" effect="plain" round>{{ bidShort(detail.bid_type) }}</el-tag>
              <el-tag size="small" :type="isCrawled(detail) ? 'primary' : 'info'" effect="plain" round>
                {{ isCrawled(detail) ? (detail.source_platform || '采集') : '手工录入' }}
              </el-tag>
              <span class="status-pill" :class="`status-pill--${detail.status}`">
                <i class="status-indicator"></i>{{ statusLabel(detail.status) }}
              </span>
              <span v-if="detail.created_at" class="muted">创建于 {{ detail.created_at }}</span>
            </div>
          </div>
        </div>

        <div class="detail-body">
          <div class="section-title">项目信息</div>
          <DetailGrid :items="[
            { label: '预算', value: detail.budget ? fmtBudgetNum(detail.budget) + ' 万' : '', mono: true },
            { label: '截止', value: fmtDate(detail.deadline) || '', mono: true },
            { label: '地区', value: detail.region },
            { label: '采购方', value: detail.purchaser },
            { label: '中标单位', value: detail.winner },
            { label: '联系人', value: detail.contact_name },
            { label: '联系方式', value: detail.contact_phone, mono: true, full: true },
            { label: '地址', value: detail.address, full: true },
            { label: '服务内容', value: detail.service_content, full: true },
          ]" />

          <div class="section-title section-title--muted">原文信息</div>
          <div class="source-row" v-if="detail.source_url">
            <div class="source-body">
              <div class="source-label">原文链接</div>
              <el-link type="primary" :href="detail.source_url" target="_blank" :underline="false" class="source-link">
                {{ detail.source_url }}
              </el-link>
            </div>
            <el-button type="primary" plain size="small" :loading="fulltextLoading" :icon="Document" @click="openFulltext">
              查看公告全文
            </el-button>
          </div>
          <div class="source-row source-row--empty" v-else>
            <span class="muted">该线索未记录原文链接</span>
          </div>
        </div>
      </template>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <template v-if="detail && detail.status === 'active'">
          <el-button @click="releaseLead(detail.id)">释放</el-button>
          <el-button type="danger" plain @click="deleteLead(detail.id)">删除</el-button>
          <el-button
            type="primary"
            @click="() => { const id = detail.id; detailVisible = false; openConvert(id) }"
          >转化此线索</el-button>
        </template>
      </template>
    </el-dialog>

    <!-- 公告全文（重排版） -->
    <el-drawer v-model="fulltextVisible" :size="isMobile ? '94%' : '680px'" class="fulltext-drawer" :with-header="false">
      <div class="ft-header">
        <div class="ft-header-body">
          <div class="ft-eyebrow">公告全文</div>
          <div class="ft-title">{{ detail?.title || '公告正文' }}</div>
          <div class="ft-meta">
            <span v-if="detail?.source_platform">{{ detail.source_platform }}</span>
            <span v-if="detail?.region"> · {{ detail.region }}</span>
            <span v-if="detail?.created_at"> · 发布于 {{ detail.created_at }}</span>
          </div>
        </div>
        <el-button text circle size="small" @click="fulltextVisible = false" class="ft-close">
          <el-icon :size="18"><Close /></el-icon>
        </el-button>
      </div>
      <div class="ft-scroll">
        <div v-loading="fulltextLoading" class="ft-article">
          <el-alert v-if="fulltextError" type="warning" :closable="false" :title="fulltextError" />
          <!-- eslint-disable-next-line vue/no-v-html -->
          <div v-else-if="fulltext" class="md-body" v-html="fulltextHtml"></div>
          <div v-else class="ft-empty muted">（无正文内容）</div>
        </div>
      </div>
      <div v-if="detail?.source_url" class="ft-footer">
        <el-link type="primary" :href="detail.source_url" target="_blank" :underline="false">
          在原文网站打开 <el-icon :size="12" style="vertical-align:-2px"><TopRight /></el-icon>
        </el-link>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Download, Loading, Document, Close, TopRight } from '@element-plus/icons-vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import PageHeader from '../components/PageHeader.vue'
import PageTable from '../components/PageTable.vue'
import FilterBar from '../components/FilterBar.vue'
import DetailGrid from '../components/DetailGrid.vue'
import { get, getList, post, put, fmtDate, fmtDateMDY, fmtNum, exportCsv } from '../api'
import { useDictStore, useCrawlStore } from '../stores/app'
import { useIsMobile } from '../composables/useIsMobile'

const dict = useDictStore()
const crawl = useCrawlStore()
const isMobile = useIsMobile()

const TABS = [
  { key: 'all', label: '全部' },
  { key: 'active', label: '待转化' },
  { key: 'pool', label: '公海池' },
  { key: 'converted', label: '已转化' },
  { key: 'abandoned', label: '已删除' },
]

const leads = ref([])
const loading = ref(false)
const tab = ref('all')
const filter = reactive({ q: '', region: '', from: '', to: '', status: '' })
const draft = reactive({ q: '', region: '', from: '', to: '', status: '' })
// 关键词全文检索命中的 id 集合；null 表示当前无关键词，不参与过滤
const matchedIds = ref(null)

const counts = computed(() => ({
  all: leads.value.length,
  active: leads.value.filter((l) => l.status === 'active').length,
  pool: leads.value.filter((l) => l.status === 'pool').length,
  converted: leads.value.filter((l) => l.status === 'converted').length,
  abandoned: leads.value.filter((l) => l.status === 'abandoned').length,
}))
const baseList = computed(() =>
  tab.value === 'all' ? leads.value : leads.value.filter((l) => l.status === tab.value),
)
const filteredList = computed(() => baseList.value.filter((l) => {
  if (filter.q && !(matchedIds.value && matchedIds.value.has(l.id))) return false
  if (filter.status && l.status !== filter.status) return false
  if (filter.region && !(l.region || '').includes(filter.region)) return false
  if (filter.from && l.created_at && l.created_at < filter.from) return false
  if (filter.to && l.created_at && l.created_at > filter.to) return false
  return true
}))
const emptyTextForTab = computed(() => ({ all: '暂无线索', active: '当前无待转化线索', pool: '公海池空空如也', converted: '还没有已转化的线索', abandoned: '没有被删除的线索' }[tab.value]))
const emptyHintForTab = computed(() => ({
  all: '点击"采集线索"自动抓取最新公告；或"手工新增"录入自己发现的线索',
  active: '点击"采集线索"自动抓取最新公告；或"手工新增"录入自己发现的线索',
  pool: '同事释放到公海的线索会出现在这里，可点击"领取"接手',
  converted: '转化成功的线索会归集到这里，可查看对应商机',
  abandoned: '删除的线索保留在此，可"恢复"回待转化',
}[tab.value]))

const isCrawled = (l) => (l.source_platform && l.source_platform !== '手动录入' && l.source_platform !== '手动新增') || !!l.source_url
const relCount = (l) => (l.related_customer_ids || '').split(',').filter(Boolean).length
const bidTagType = (t) => (/中标|成交/.test(t || '') ? 'success' : t ? 'warning' : 'info')
// 类别精简：去掉"公告"式后缀，长名称映射为短标签（值仍用完整 bid_type 提交/排序）
const BID_TYPE_SHORT = {
  '公开招标公告': '招标', '邀请招标公告': '招标', '资格预审公告': '预审',
  '竞争性磋商公告': '磋商', '竞争性谈判公告': '谈判', '询价公告': '询价', '竞价公告': '竞价',
  '中标公告': '中标', '中标公示': '中标', '成交公告': '成交', '结果公告': '结果',
  '更正公告': '更正', '澄清公告': '澄清', '废标公告': '废标', '终止公告': '废标', '流标公告': '废标',
  '其他公告': '其他',
}
const bidShort = (t) => (!t ? '待分类' : BID_TYPE_SHORT[t] || t.replace(/(公告|公示)$/, '') || t)
// 少量历史数据把单位写进了数值（"78.62万"），列头已带(万)，展示前去尾缀
const fmtBudgetNum = (v) => fmtNum(String(v).replace(/[^\d.\-]/g, ''))
const statusLabel = (s) => ({ converted: '已转化', abandoned: '已删除', pool: '公海池' }[s] || '待转化')
const statusType = (s) => ({ converted: 'success', abandoned: 'danger', pool: 'warning' }[s] || 'primary')
const splitKw = (s) => (s || '').split(/[,，;；]/).map((x) => x.trim()).filter(Boolean)

async function load() {
  loading.value = true
  leads.value = await getList('/leads')
  loading.value = false
}
async function applyFilter() {
  Object.assign(filter, draft)
  if (filter.q) {
    const r = await get('/leads/search?q=' + encodeURIComponent(filter.q))
    matchedIds.value = new Set((r && r.ids) || [])
  } else {
    matchedIds.value = null
  }
}
function resetFilter() {
  Object.assign(draft, { q: '', region: '', from: '', to: '', status: '' })
  Object.assign(filter, draft)
  matchedIds.value = null
}
async function doCrawl() {
  const msg = await crawl.start()
  if (msg) ElMessage.error(msg)
  else ElMessage.info('采集已启动，正在抓取并 AI 分析…')
}
watch(() => crawl.finishedAt, () => { load(); dict.loadCustomers() })

// ---- 行操作 ----
async function claimLead(id) {
  const r = await post(`/leads/${id}/claim`, { assignee: '万升航控' })
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success(r.message || '已领取'); load()
}
async function releaseLead(id) {
  const res = await ElMessageBox.prompt('释放原因（会显示在公海池列表）:', '释放至公海', {
    inputPlaceholder: '如：地区不符 / 暂无跟进人力 / 已有同事对接',
    inputValidator: (v) => !!v?.trim() || '请填写释放原因',
  }).catch(() => null)
  if (!res) return
  const r = await post(`/leads/${id}/release`, { reason: res.value.trim() })
  if (r.error) return ElMessage.error(r.error)
  detailVisible.value = false
  ElMessage.success(r.message || '已释放至公海池'); load()
}
async function deleteLead(id) {
  const res = await ElMessageBox.prompt('删除原因（保留在"已删除"，可恢复）:', '删除线索', {
    inputPlaceholder: '如：重复线索 / 与业务无关 / 信息有误',
    inputValidator: (v) => !!v?.trim() || '请填写删除原因',
  }).catch(() => null)
  if (!res) return
  const r = await post(`/leads/${id}/abandon`, { reason: res.value.trim() })
  if (r.error) return ElMessage.error(r.error)
  detailVisible.value = false
  ElMessage.success(r.message || '已删除'); load()
}
async function restoreLead(id) {
  try { await ElMessageBox.confirm('确认恢复该线索为待转化？', '恢复线索') } catch (e) { return }
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
  if (id) get(`/leads/${id}`).then((l) => { Object.keys(form).forEach((k) => (form[k] = l[k] ?? form[k])) })
  formVisible.value = true
}
async function saveForm() {
  if (!form.title) return ElMessage.error('请输入标题')
  const r = editId.value ? await put(`/leads/${editId.value}`, form) : await post('/leads', form)
  if (r.error) return ElMessage.error(r.error)
  ElMessage.success(editId.value ? '更新成功' : '创建成功')
  formVisible.value = false
  load()
}

// ---- 详情 ----
const detailVisible = ref(false)
const detail = ref(null)
async function viewDetail(id) {
  const r = await get(`/leads/${id}`)
  if (r.error) return ElMessage.error('加载线索详情失败：' + r.error)
  detail.value = r
  detailVisible.value = true
}

// ---- 全文 ----
const fulltextVisible = ref(false)
const fulltextLoading = ref(false)
const fulltext = ref('')
const fulltextError = ref('')
const fulltextHtml = computed(() => DOMPurify.sanitize(marked.parse(fulltext.value || '')))
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
/* ---- 顶部 tabs ---- */
.tabs-bar {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; margin-bottom: 12px; flex-wrap: wrap;
}
.seg-group {
  display: inline-flex; padding: 4px; gap: 2px;
  background: var(--crm-slate-100);
  border-radius: 10px;
  border: 1px solid var(--crm-border-soft);
}
.seg-btn {
  display: inline-flex; align-items: center; gap: 7px;
  padding: 7px 18px; height: 38px;
  border: none; background: transparent; cursor: pointer;
  font-family: inherit; font-size: 15px; font-weight: 600;
  color: var(--crm-fg-3);
  border-radius: 8px;
  transition: all var(--crm-dur-fast) var(--crm-ease-out);
  letter-spacing: -0.005em;
}
.seg-btn:hover { color: var(--crm-fg-1); }
.seg-btn.is-active {
  background: var(--crm-bg-card); color: var(--crm-pine-600);
  box-shadow: var(--crm-shadow-sm);
  font-weight: 700;
}
.seg-count {
  font-family: var(--crm-font-mono); font-size: 12.5px; font-weight: 600;
  padding: 1px 7px; height: 19px; line-height: 17px;
  background: var(--crm-slate-200); color: var(--crm-fg-3);
  border-radius: 10px; min-width: 24px;
}
.seg-btn.is-active .seg-count { background: var(--crm-pine-100); color: var(--crm-pine-600); }
.tabs-hint { font-size: 12px; }

/* ---- 采集 alert ---- */
.crawl-alert { margin-bottom: 12px; }
.crawl-line { display: flex; align-items: center; gap: 10px; font-size: 12.5px; flex-wrap: wrap; }
.crawl-count { margin-left: auto; }
.crawl-count b { font-family: var(--crm-font-mono); color: var(--crm-pine-600); font-size: 14px; }

/* ---- 表格容器 ---- */
.table-wrap {
  background: var(--crm-bg-card);
  border: 1px solid var(--crm-border-soft);
  border-radius: var(--crm-radius-lg);
  overflow: hidden;
  box-shadow: var(--crm-shadow-xs);
}

/* ---- 单元格 ---- */
.serial { font-size: 12px; color: var(--crm-fg-3); letter-spacing: -0.02em; }
.cell-title { display: flex; align-items: center; gap: 8px; justify-content: space-between; }
.cell-title-text {
  flex: 1; min-width: 0;
  color: var(--crm-fg-1); font-weight: 500; font-size: 13.5px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  line-height: 1.45;
}
.cell-title-text.is-link {
  cursor: pointer; text-decoration: underline;
  text-underline-offset: 2px; text-decoration-thickness: 1px;
  text-decoration-color: var(--crm-border-strong);
}
.cell-title-text.is-link:hover { color: var(--crm-pine-600); text-decoration-color: var(--crm-pine-600); }
.cell-meta {
  font-size: 11.5px; color: var(--crm-fg-3); margin-top: 3px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.rel-tag { margin-left: 4px; }
.budget { color: var(--crm-fg-1); font-weight: 600; font-size: 13px; }
.region-text { color: var(--crm-fg-2); }
.date { font-size: 12px; }
.date.is-urgent { color: var(--crm-rose-500); font-weight: 600; }
.reason-cell { font-size: 12px; }
.row-actions { display: inline-flex; gap: 0; justify-content: flex-end; align-items: center; }
.row-actions :deep(.el-button.is-link) { padding: 2px 6px; }

/* ---- 状态胶囊 ---- */
.status-pill {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 2px 8px 2px 6px;
  font-size: 11.5px; font-weight: 500;
  border-radius: var(--crm-radius-full);
  background: var(--crm-slate-100); color: var(--crm-fg-2);
  letter-spacing: -0.005em;
  white-space: nowrap;
}
.status-indicator { width: 6px; height: 6px; border-radius: 50%; background: currentColor; opacity: 0.9; }
.status-pill--active    { background: var(--crm-pine-25); color: var(--crm-pine-600); }
.status-pill--converted { background: var(--crm-sky-50); color: var(--crm-sky-500); }
.status-pill--pool      { background: var(--crm-amber-50); color: var(--crm-amber-500); }
.status-pill--abandoned { background: var(--crm-slate-100); color: var(--crm-fg-3); }

/* ---- 表单：分组 ---- */
.form-section { margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px dashed var(--crm-border-soft); }
.form-section:last-child { margin-bottom: 0; padding-bottom: 0; border-bottom: none; }
.conv-alert { margin-bottom: 12px; }
.field-hint { font-size: 11.5px; color: var(--crm-fg-4); margin-left: 98px; margin-top: -6px; }
@media (max-width: 768px) { .field-hint { margin-left: 0; } }

/* ---- 详情弹窗 ---- */
.detail-dialog :deep(.el-dialog__body) { padding: 0 !important; }
.detail-hero {
  display: flex; align-items: flex-start; gap: 20px;
  padding: 14px 20px 12px;
  background: linear-gradient(180deg, var(--crm-pine-25) 0%, var(--crm-bg-card) 100%);
  border-bottom: 1px solid var(--crm-border-soft);
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
.detail-hero-meta .serial { font-size: 11.5px; padding: 1px 6px; background: var(--crm-slate-100); border-radius: var(--crm-radius-sm); }
.detail-hero-side { flex-shrink: 0; display: flex; flex-direction: column; align-items: center; gap: 4px; }
.match-ring {
  --size: 64px; --thickness: 4px;
  width: var(--size); height: var(--size);
  border-radius: 50%;
  display: flex; align-items: baseline; justify-content: center; padding-top: 18px;
  background:
    conic-gradient(var(--ring) calc(var(--ring-percent) * 1%), var(--crm-slate-100) 0);
  position: relative;
}
.match-ring::before {
  content: ''; position: absolute; inset: 6px; border-radius: 50%; background: var(--crm-bg-card);
}
.match-num { position: relative; font-family: var(--crm-font-display); font-size: 20px; font-weight: 700; color: var(--crm-fg-1); letter-spacing: -0.02em; }
.match-unit { position: relative; font-size: 11px; color: var(--crm-fg-3); margin-left: 1px; }
.match-level { font-size: 11.5px; color: var(--crm-fg-3); font-weight: 500; }

.detail-body { padding: 14px 20px 8px; }

.kw-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.match-reason {
  font-size: 13px; color: var(--crm-fg-2); line-height: 1.7;
  padding: 10px 14px; background: var(--crm-slate-25);
  border-left: 3px solid var(--crm-pine-300);
  border-radius: 0 var(--crm-radius-sm) var(--crm-radius-sm) 0;
  margin-bottom: 8px;
}

/* 原文链接 */
.source-row {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px;
  background: var(--crm-slate-25);
  border: 1px solid var(--crm-border-soft);
  border-radius: var(--crm-radius-md);
  margin-top: 8px;
}
.source-row--empty { color: var(--crm-fg-4); font-size: 12.5px; justify-content: center; padding: 12px; }
.source-body { flex: 1; min-width: 0; }
.source-label { font-size: 11.5px; color: var(--crm-fg-3); margin-bottom: 2px; letter-spacing: -0.005em; }
.source-link { font-size: 12.5px; word-break: break-all; }

/* ---- 全文抽屉 ---- */
.fulltext-drawer :deep(.el-drawer__body) { padding: 0 !important; display: flex; flex-direction: column; }
.ft-header {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 18px 24px 14px;
  border-bottom: 1px solid var(--crm-border-soft);
  background: var(--crm-bg-card);
  flex-shrink: 0;
}
.ft-header-body { flex: 1; min-width: 0; }
.ft-eyebrow {
  font-size: 10.5px; font-weight: 600; letter-spacing: 0.08em;
  color: var(--crm-pine-600); text-transform: uppercase;
  margin-bottom: 4px;
}
.ft-title {
  font-family: var(--crm-font-display);
  font-size: 15px; font-weight: 600; color: var(--crm-fg-1);
  line-height: 1.35; letter-spacing: -0.011em;
  word-break: break-word; overflow-wrap: anywhere;
}
.ft-meta { margin-top: 6px; font-size: 12px; color: var(--crm-fg-3); }
.ft-close { flex-shrink: 0; margin-top: 2px; }
.ft-scroll {
  flex: 1; overflow-y: auto; background: var(--crm-bg-card);
}
.ft-article {
  max-width: 720px; margin: 0 auto;
  padding: 32px 40px 60px;
}
/* ---- 正文精细化排版（marked 渲染结果经 v-html 注入，需 :deep 穿透 scoped） ---- */
.md-body { font-size: 14.5px; line-height: 1.95; color: var(--crm-fg-2); word-break: break-word; overflow-wrap: anywhere; }
.md-body :deep(h1) {
  font-size: 20px; font-weight: 700; color: var(--crm-fg-1);
  line-height: 1.5; letter-spacing: -0.015em;
  margin: 0 0 24px; padding-bottom: 14px;
  border-bottom: 2px solid var(--crm-pine-50);
}
.md-body :deep(h2) {
  font-size: 16.5px; font-weight: 700; color: var(--crm-pine-700);
  line-height: 1.55; margin: 32px 0 12px;
  padding-left: 10px; border-left: 4px solid var(--crm-pine-500);
}
.md-body :deep(h3) {
  font-size: 15px; font-weight: 650; color: var(--crm-fg-1);
  line-height: 1.6; margin: 28px 0 10px;
}
.md-body :deep(h1 + h2), .md-body :deep(h1 + h3), .md-body :deep(h2 + h3) { margin-top: 12px; }
.md-body :deep(p) { margin: 0 0 13px; text-align: justify; }
.md-body :deep(strong) { color: var(--crm-fg-1); font-weight: 650; }
.md-body :deep(ul), .md-body :deep(ol) { margin: 0 0 16px; padding-left: 24px; }
.md-body :deep(li) { margin: 5px 0; padding-left: 2px; }
.md-body :deep(ul li::marker) { color: var(--crm-pine-400); }
.md-body :deep(ol li::marker) { color: var(--crm-pine-600); font-weight: 650; }
.md-body :deep(li p) { margin: 0; }
.md-body :deep(li > strong:first-child) { color: var(--crm-pine-700); }
.md-body :deep(table) {
  width: 100%; border-collapse: collapse; margin: 14px 0 18px;
  font-size: 13.5px; line-height: 1.7;
}
.md-body :deep(th), .md-body :deep(td) {
  border: 1px solid var(--crm-border-hairline); padding: 8px 12px; text-align: left;
}
.md-body :deep(th) { background: var(--crm-pine-25); color: var(--crm-pine-800); font-weight: 650; }
.md-body :deep(tbody tr:nth-child(even) td) { background: var(--crm-slate-25); }
.md-body :deep(blockquote) {
  margin: 14px 0; padding: 10px 16px;
  background: var(--crm-slate-25); border-left: 3px solid var(--crm-pine-200);
  border-radius: 0 var(--crm-radius-sm) var(--crm-radius-sm) 0;
  color: var(--crm-fg-3);
}
.md-body :deep(hr) { border: none; border-top: 1px dashed var(--crm-border-strong); margin: 26px 0; }
.md-body :deep(a) { color: var(--crm-pine-600); text-decoration: none; border-bottom: 1px solid var(--crm-pine-100); }
.md-body :deep(a:hover) { color: var(--crm-pine-400); border-bottom-color: var(--crm-pine-400); }
.md-body :deep(code) {
  font-family: var(--crm-font-mono); font-size: 12.5px;
  background: var(--crm-bg-subtle); padding: 1px 6px; border-radius: var(--crm-radius-xs);
  color: var(--crm-fg-1);
}
.ft-empty { padding: 60px 0; text-align: center; }
.ft-footer {
  padding: 12px 24px;
  border-top: 1px solid var(--crm-border-soft);
  background: var(--crm-slate-25);
  text-align: right;
  flex-shrink: 0;
}
@media (max-width: 768px) {
  .ft-article { padding: 24px 20px 40px; }
  .detail-hero { padding: 16px 18px; gap: 12px; }
  .detail-hero-side { display: none; }
  .detail-body { padding: 16px 18px 0; }
}
</style>
