// 统一的前端 API 客户端：所有请求走同源 /api，携带 session cookie
const API_BASE = '/api'

async function request(path, options = {}) {
  const opts = {
    method: options.method || 'GET',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...options,
  }
  const res = await fetch(API_BASE + path, opts)
  let data = null
  try {
    data = await res.json()
  } catch (e) {
    data = null
  }
  if (!res.ok) {
    const err = new Error((data && data.error) || `请求失败 (${res.status})`)
    err.status = res.status
    throw err
  }
  return data
}

export const api = {
  get: (p) => request(p),
  post: (p, body) => request(p, { method: 'POST', body: JSON.stringify(body) }),
  put: (p, body) => request(p, { method: 'PUT', body: JSON.stringify(body) }),
  del: (p) => request(p, { method: 'DELETE' }),
}

export async function fetchMe() {
  try {
    const data = await api.get('/auth/me')
    return data.user
  } catch (e) {
    return null
  }
}

export async function login(username, password, remember) {
  const data = await api.post('/auth/login', { username, password, remember })
  return data.user
}

export async function logout() {
  try {
    await api.post('/auth/logout', {})
  } catch (e) {
    /* ignore */
  }
}
