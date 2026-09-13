import { defineStore } from 'pinia'
import { get, post, STAGES_FALLBACK } from '../api'

// 字典 store：多页面共用的客户/联系人/商机/阶段/选项下拉数据
export const useDictStore = defineStore('dict', {
  state: () => ({
    customers: [],
    contacts: [],
    opportunities: [],
    stageNames: [...STAGES_FALLBACK],
    options: { customer_types: [], customer_levels: [], regions: [] },
  }),
  actions: {
    async loadCustomers() { this.customers = (await get('/customers')) || [] },
    async loadContacts() { this.contacts = (await get('/contacts')) || [] },
    async loadOpportunities() { this.opportunities = (await get('/opportunities')) || [] },
    async loadStages() {
      const st = await get('/stages')
      if (Array.isArray(st) && st.length) {
        this.stageNames = st.slice().sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0)).map((s) => s.name)
      }
    },
    async loadOptions() { this.options = (await get('/options')) || this.options },
    // 按客户过滤联系人（级联下拉）
    contactsOf(customerId) {
      if (!customerId) return this.contacts
      return this.contacts.filter((c) => String(c.customer_id) === String(customerId))
    },
  },
})

// 采集任务 store：后台采集 + 6 秒轮询，页面 watch finishedAt 刷新数据
export const useCrawlStore = defineStore('crawl', {
  state: () => ({
    running: false, phase: '', progress: 0, total: 0, current: '',
    count: 0, message: '', errors: [], finishedAt: 0, _timer: null,
  }),
  actions: {
    async start() {
      const r = await post('/crawl')
      if (r.running) {
        this.running = true
        this.beginPoll()
        return ''
      }
      if (r.ok) return r.message || '采集完成'
      return r.error || '启动失败'
    },
    beginPoll() {
      if (this._timer) return
      this.running = true
      this._timer = setInterval(async () => {
        const s = await get('/crawl/status')
        if (!s || s.error) return
        Object.assign(this, {
          running: s.running, phase: s.phase || '', progress: s.progress || 0,
          total: s.total || 0, current: s.current || '', count: s.count || 0,
        })
        if (!s.running) {
          clearInterval(this._timer)
          this._timer = null
          this.message = s.message || '采集完成'
          this.errors = s.errors || []
          this.finishedAt = Date.now()
        }
      }, 6000)
    },
    async checkRunning() { // 页面加载时恢复进行中的轮询
      const s = await get('/crawl/status')
      if (s && !s.error && s.running) this.beginPoll()
    },
  },
})
