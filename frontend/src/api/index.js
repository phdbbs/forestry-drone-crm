// 统一请求层：永不抛错，失败返回 { error }。
//
// ⚠️ 重要约定：失败时返回的是 `{ error: '...' }` 对象，**不是数组**。
// 列表接口请一律用 getList()，它保证返回数组——否则
// `data = (await get('/x')) || []` 会把 truthy 的 { error } 当成数组，
// 后续 .filter()/.map() 直接抛错导致白屏。
export async function request(path, opts = {}) {
  try {
    const res = await fetch('/api' + path, {
      ...opts,
      // headers 合并放在 opts 之后，避免调用方传 headers 时整体覆盖 Content-Type
      headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    })
    let data = null
    try { data = await res.json() } catch (e) { /* 204/空响应 */ }
    if (!res.ok) {
      return { error: (data && data.error) || `请求失败 (HTTP ${res.status})` }
    }
    return data || {}
  } catch (e) {
    return { error: '网络异常: ' + e.message }
  }
}

export const get = (path, opts) => request(path, opts)
export const post = (path, body, opts) => request(path, { method: 'POST', body: JSON.stringify(body || {}), ...opts })
export const put = (path, body, opts) => request(path, { method: 'PUT', body: JSON.stringify(body || {}), ...opts })
export const del = (path, opts) => request(path, { method: 'DELETE', ...opts })

/**
 * 列表接口专用：保证返回数组。
 * 失败时返回空数组，调用方再通过返回值的长度或另行判错处理。
 */
export async function getList(path, opts) {
  const r = await request(path, opts)
  return Array.isArray(r) ? r : []
}

export function fmtDate(d) { return d ? String(d).substring(0, 10) : '' }

/**
 * 数值格式化：113.268083 → "113.27"，100 → "100"，空值 → "-"。
 * 用于金额/预算等列，避免表格里出现一长串小数。
 */
export function fmtNum(v, digits = 2) {
  if (v === null || v === undefined || v === '') return '-'
  const n = Number(v)
  if (!Number.isFinite(n)) return String(v)
  // 先 toFixed 保证字符串含小数点，再去掉尾随 0 与孤立的小数点
  return n.toFixed(digits).replace(/\.?0+$/, '') || '0'
}

/** 金额（万元）格式化，带单位 */
export function fmtAmount(v, digits = 2) {
  const s = fmtNum(v, digits)
  return s === '-' ? '-' : s + '万'
}

// CSV 导出（带 BOM、中文文件名），list 为当前筛选结果
export async function exportCsv(type, list) {
  if (!list || !list.length) return '当前无数据可导出'
  try {
    const res = await fetch('/api/export/' + type, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids: list.map((x) => x.id) }),
    })
    if (!res.ok) {
      let msg = '导出失败'
      try { msg = (await res.json()).error || msg } catch (e) {}
      return msg
    }
    const blob = await res.blob()
    const cd = res.headers.get('Content-Disposition') || ''
    const m = cd.match(/filename\*=UTF-8''(.+)/)
    const name = m ? decodeURIComponent(m[1]) : `${type}_${new Date().toISOString().slice(0, 10)}.csv`
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = name
    document.body.appendChild(a)
    a.click()
    setTimeout(() => { URL.revokeObjectURL(url); a.remove() }, 100)
    return ''
  } catch (e) {
    return '导出异常: ' + e.message
  }
}

// 语义色统一走 Element Plus 变量，避免与主题脱钩
export const matchColor = (score) => (score >= 80 ? 'var(--el-color-success)' : score >= 60 ? 'var(--el-color-warning)' : score >= 40 ? 'var(--el-color-primary)' : 'var(--el-color-danger)')
export const probColor = (p) => (p >= 80 ? 'var(--el-color-success)' : p >= 50 ? 'var(--el-color-warning)' : p >= 30 ? 'var(--el-color-primary)' : 'var(--el-color-danger)')
export const STAGES_FALLBACK = ['初步接触', '需求确认', '方案报价', '商务谈判', '合同签订']
export const STAGE_COLORS = [
  'var(--el-color-info)',
  'var(--el-color-primary)',
  'var(--el-color-warning)',
  'var(--el-color-success)',
  'var(--el-color-danger)',
]
export const stageColor = (name, names) => {
  const i = (names || STAGES_FALLBACK).indexOf(name)
  return STAGE_COLORS[i >= 0 ? i % STAGE_COLORS.length : 0]
}
export const ROLE_OPTIONS = ['决策人', '业务负责人', '技术对接', '采购执行']
export const METHOD_OPTIONS = ['电话', '视频会议', '现场拜访', '微信', '邮件']
