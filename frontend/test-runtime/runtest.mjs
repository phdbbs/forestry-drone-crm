// 运行时冒烟测试：jsdom 中加载 IIFE 打包产物，逐路由导航 + 常见点击，抓 window/Vue 错误
import fs from 'fs'
import { JSDOM, VirtualConsole } from 'jsdom'

const API = process.env.API_BASE || 'http://127.0.0.1:5011'
const bundle = fs.readFileSync(new URL('./app.iife.js', import.meta.url), 'utf8')

const errors = []
const vc = new VirtualConsole()
vc.on('jsdomError', (e) => errors.push('JSDOM: ' + ((e.detail && e.detail.stack) || e.message)))
vc.on('error', (...a) => errors.push('console.error: ' + a.map(String).join(' ').slice(0, 400)))
vc.on('warn', (...a) => { const s = a.map(String).join(' '); if (s.includes('Failed to resolve') || s.includes('injection')) errors.push('console.warn: ' + s.slice(0, 250)) })

const dom = new JSDOM('<!doctype html><html><body><div id="app"></div></body></html>', {
  url: 'http://localhost:5003/#/dashboard',
  runScripts: 'dangerously',
  pretendToBeVisual: true,
  virtualConsole: vc,
})
const win = dom.window

win.addEventListener('error', (e) => errors.push('window.error: ' + ((e.error && e.error.stack) || e.message)))
win.addEventListener('unhandledrejection', (e) => errors.push('rejection: ' + ((e.reason && (e.reason.stack || e.reason.message)) || e.reason)))

win.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
win.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} takeRecords() { return [] } }
if (!win.matchMedia) {
  win.matchMedia = (q) => ({ matches: false, media: q, onchange: null, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, dispatchEvent() { return false } })
}
win.fetch = (u, o) => fetch(String(u).startsWith('http') ? u : API + u, o)
win.URL.createObjectURL = () => 'blob:stub'
win.URL.revokeObjectURL = () => {}

const s = win.document.createElement('script')
s.textContent = bundle
win.document.body.appendChild(s)

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const snap = () => {
  const doc = win.document
  const rows = doc.querySelectorAll('.el-table__row').length
  const main = doc.querySelector('.main-content') || doc.body
  const text = (main.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 70)
  return { rows, text }
}

const ROUTES = ['/dashboard', '/leads', '/opportunities', '/contacts', '/customers', '/contactlog', '/followups', '/kanban', '/reports', '/settings']

await sleep(2500)
const report = []
for (const rt of ROUTES) {
  const before = errors.length
  win.location.hash = '#' + rt
  await sleep(2200)
  const s1 = snap()
  report.push(`${rt.padEnd(16)} rows=${String(s1.rows).padStart(3)} newErr=${errors.length - before}  "${s1.text}"`)
}

// —— 点击行为测试 ——
async function clickAndCheck(name, sel, waitSel, ms = 1200) {
  const before = errors.length
  const el = win.document.querySelector(sel)
  if (!el) { report.push(`CLICK ${name}: selector not found: ${sel}`); return }
  el.dispatchEvent(new win.MouseEvent('click', { bubbles: true }))
  await sleep(ms)
  const ok = waitSel ? !!win.document.querySelector(waitSel) : true
  report.push(`CLICK ${name}: targetVisible=${ok} newErr=${errors.length - before}`)
  // 关闭可能的弹窗
  const closeBtn = win.document.querySelector('.el-dialog__headerbtn')
  if (closeBtn) closeBtn.dispatchEvent(new win.MouseEvent('click', { bubbles: true }))
  await sleep(400)
}

await clickAndCheck('客户行详情', '.main-content .el-table__row', '.el-overlay-dialog .detail-hero, .el-dialog', 1500)
await clickAndCheck('联系人行详情', '.main-content .el-table__row', '.el-overlay-dialog, .el-dialog', 1500)

console.log('===== ROUTE/CLICK REPORT =====')
report.forEach((r) => console.log(r))
console.log('===== ERRORS (' + errors.length + ') =====')
const seen = new Set()
for (const e of errors) {
  const key = e.slice(0, 120)
  if (seen.has(key)) continue
  seen.add(key)
  console.log('- ' + e.replace(/\n/g, ' | ').slice(0, 500))
}
process.exit(0)
