import { defineStore } from 'pinia'
import { get, getList, post, STAGES_FALLBACK } from '../api'

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
    // 一律用 getList()：get() 失败时返回 truthy 的 { error } 对象，
    // `get() || []` 挡不住它，后续 .filter()/.map() 直接抛错（点击无反应的元凶）
    async loadCustomers() { this.customers = await getList('/customers') },
    async loadContacts() { this.contacts = await getList('/contacts') },
    async loadOpportunities() { this.opportunities = await getList('/opportunities') },
    async loadStages() {
      const st = await get('/stages')
      if (Array.isArray(st) && st.length) {
        this.stageNames = st.slice().sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0)).map((s) => s.name)
      }
    },
    async loadOptions() {
      const o = await get('/options')
      if (o && !o.error && typeof o === 'object') this.options = { ...this.options, ...o }
    },
    // 按客户过滤联系人（级联下拉）
    contactsOf(customerId) {
      const list = Array.isArray(this.contacts) ? this.contacts : []
      if (!customerId) return list
      return list.filter((c) => String(c.customer_id) === String(customerId))
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
