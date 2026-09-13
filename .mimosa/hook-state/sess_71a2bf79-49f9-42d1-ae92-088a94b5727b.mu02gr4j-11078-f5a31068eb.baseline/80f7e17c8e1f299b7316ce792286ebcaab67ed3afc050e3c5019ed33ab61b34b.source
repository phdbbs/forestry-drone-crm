// 与原版语义一致：永不抛错，失败返回 {error}
export async function request(path, opts = {}) {
  try {
    const res = await fetch('/api' + path, {
      headers: { 'Content-Type': 'application/json' },
      ...opts,
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

export const get = (path) => request(path)
export const post = (path, body) => request(path, { method: 'POST', body: JSON.stringify(body || {}) })
export const put = (path, body) => request(path, { method: 'PUT', body: JSON.stringify(body || {}) })
export const del = (path) => request(path, { method: 'DELETE' })

export function fmtDate(d) { return d ? String(d).substring(0, 10) : '' }

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

export const matchColor = (score) => (score >= 80 ? '#166534' : score >= 60 ? '#f59e0b' : score >= 40 ? '#3b82f6' : '#ef4444')
export const probColor = (p) => (p >= 80 ? '#166534' : p >= 50 ? '#f59e0b' : p >= 30 ? '#3b82f6' : '#ef4444')
export const STAGES_FALLBACK = ['初步接触', '需求确认', '方案报价', '商务谈判', '合同签订']
export const STAGE_COLORS = ['#94a3b8', '#3b82f6', '#f59e0b', '#8b5cf6', '#166534']
export const stageColor = (name, names) => {
  const i = (names || STAGES_FALLBACK).indexOf(name)
  return STAGE_COLORS[i >= 0 ? i % STAGE_COLORS.length : 0]
}
export const ROLE_OPTIONS = ['决策人', '业务负责人', '技术对接', '采购执行']
export const METHOD_OPTIONS = ['电话', '视频会议', '现场拜访', '微信', '邮件']
