// 用真实部署的 ESM 分块产物（非 IIFE）在 jsdom + Node ESM 下运行，
// 专门暴露 chunk 间循环依赖 / TDZ / 动态 import 失败这类“分块模式独有”的问题。
import fs from 'fs'
import path from 'path'
import { pathToFileURL } from 'url'
import { JSDOM, VirtualConsole } from 'jsdom'

const DIST = process.argv[2] || '/sessions/e82c25d316fadff5/mnt/CRM/app/static/dist'
const API = process.env.API_BASE || 'http://127.0.0.1:5011'

const errors = []
const vc = new VirtualConsole()
vc.on('jsdomError', (e) => errors.push('JSDOM: ' + ((e.detail && e.detail.stack) || e.message).slice?.(0, 400) || String(e).slice(0, 300)))
vc.on('error', (...a) => errors.push('console.error: ' + a.map(String).join(' ').slice(0, 400)))
vc.on('warn', (...a) => errors.push('warn: ' + a.map(String).join(' ').slice(0, 400)))

const dom = new JSDOM('<!doctype html><html><body><div id="app"></div></body></html>', {
  url: API + '/#/dashboard',
  runScripts: 'dangerously',
  pretendToBeVisual: true,
  virtualConsole: vc,
})
const win = dom.window

// 把 jsdom 窗口对象暴露成 Node 全局（真实分块在 Node 里以 ESM 执行）
for (const key of Object.getOwnPropertyNames(win)) {
  if (key in globalThis) continue
  try {
    Object.defineProperty(globalThis, key, { value: win[key], writable: true, configurable: true })
  } catch (e) { /* skip protected */ }
}
globalThis.window = win
globalThis.document = win.document
globalThis.navigator = win.navigator
globalThis.location = win.location
globalThis.localStorage = win.localStorage
globalThis.sessionStorage = win.sessionStorage
globalThis.HTMLElement = win.HTMLElement
globalThis.Element = win.Element
globalThis.Node = win.Node
globalThis.CustomEvent = win.CustomEvent
globalThis.Event = win.Event
globalThis.MouseEvent = win.MouseEvent
globalThis.getComputedStyle = win.getComputedStyle.bind(win)
globalThis.requestAnimationFrame = win.requestAnimationFrame.bind(win)
globalThis.cancelAnimationFrame = win.cancelAnimationFrame.bind(win)
globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
globalThis.matchMedia = win.matchMedia || ((q) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} }))
const nativeFetch = globalThis.fetch
globalThis.fetch = (u, o) => {
  const url = new URL(String(u), win.location.href).href
  if (process.env.FETCH_DEBUG) console.log('FETCH:', url)
  return nativeFetch(url, o).catch((e) => {
    console.log('FETCHFAIL:', url, '::', e.message, ':: cause:', e.cause ? (e.cause.message || e.cause.code || String(e.cause)) : '-')
    throw e
  })
}

process.on('uncaughtException', (e) => errors.push('uncaught: ' + (e.stack || e.message).slice(0, 500)))
process.on('unhandledRejection', (e) => errors.push('rejection: ' + ((e && (e.stack || e.message)) || String(e)).slice(0, 500)))
win.addEventListener('error', (e) => errors.push('window.error: ' + ((e.error && e.error.stack) || e.message).slice(0, 500)))
// 应用在 Node ESM 里运行，Vue 的 warn/error 走 Node console，不经过 jsdom virtualConsole
console.warn = (...a) => { errors.push('warn: ' + a.map(String).join(' ').slice(0, 400)) }
console.error = (...a) => { errors.push('node console.error: ' + a.map(String).join(' ').slice(0, 400)) }

// 入口 chunk：从 index.html 的 <script type="module"> 解析，避免误匹配其它 index-* 分块
const html = fs.readFileSync(path.join(DIST, 'index.html'), 'utf8')
const m = html.match(/<script[^>]+src="\/assets\/(index-[^"]+\.js)"/)
const entry = m && m[1]
if (!entry) { console.error('Cannot find module entry in index.html'); process.exit(2) }
console.log('entry chunk:', entry)
await import(pathToFileURL(path.join(DIST, 'assets', entry)).href)

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
await sleep(2500)

const appEl = win.document.querySelector('#app')
console.log('MOUNT DEBUG: #app innerHTML length =', appEl ? appEl.innerHTML.length : 'NO #app')
console.log('MOUNT DEBUG head:', appEl ? appEl.innerHTML.replace(/\s+/g, ' ').slice(0, 200) : '-')
console.log('MOUNT DEBUG errors so far:', errors.length)
for (const e of errors) console.log('  E:', e.slice(0, 240))

// 探针：视图 chunk 直接 import 是 resolve、抛错、还是永久挂起？
{
  const chunkFile = 'Dashboard-ssQXteYu.js'
  const url = pathToFileURL(path.join(DIST, 'assets', chunkFile)).href
  let done = false
  const p = import(url).then((mm) => { done = true; console.log('PROBE RESOLVED', chunkFile, 'exports:', Object.keys(mm).join(',')) })
    .catch((e) => { done = true; console.log('PROBE THREW', chunkFile, '::', e.constructor.name, '::', String(e.message).slice(0, 300)) })
  await Promise.race([p, sleep(6000)])
  if (!done) console.log('PROBE HANGING (promise pending after 6s):', chunkFile)
}

const ROUTES = ['/dashboard', '/leads', '/opportunities', '/contacts', '/customers', '/contactlog', '/followups', '/kanban', '/reports', '/settings']
for (const rt of ROUTES) {
  const before = errors.length
  win.location.hash = '#' + rt
  win.dispatchEvent(new win.HashChangeEvent('hashchange'))
  await sleep(2000)
  const rows = win.document.querySelectorAll('.el-table__row').length
  const appLen = (win.document.querySelector('#app')?.innerHTML || '').length
  const mainSel = win.document.querySelector('main, .main-content, .page, .el-main')
  const text = (mainSel?.textContent || win.document.querySelector('#app')?.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 60)
  console.log(`${rt.padEnd(16)} rows=${String(rows).padStart(3)} appLen=${String(appLen).padStart(6)} newErr=${errors.length - before}  "${text}"`)
}

console.log('===== ERRORS (' + errors.length + ') =====')
const seen = new Set()
for (const e of errors) {
  const k = e.slice(0, 140)
  if (seen.has(k)) continue
  seen.add(k)
  console.log('- ' + e.replace(/\n/g, ' | ').slice(0, 600))
}
process.exit(0)
