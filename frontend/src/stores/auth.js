import { defineStore } from 'pinia'
import { get, post } from '../api'

// 多账号鉴权 store：登录态只在内存 + 服务端 session，前端不存任何口令。
// user 由后端 /auth/status、/auth/login、/auth/me 下发，只含 id/username/display_name/role。
export const useAuthStore = defineStore('auth', {
  state: () => ({
    ready: false,        // 是否已拿到 /auth/status
    authEnabled: true,   // 服务端是否启用鉴权
    configured: true,    // 是否已创建过账号（false 走「首次初始化管理员」）
    authenticated: false,
    user: null,
  }),
  getters: {
    isAdmin: (s) => !!s.user && s.user.role === 'admin',
    displayName: (s) => (s.user && (s.user.display_name || s.user.username)) || '',
    initials: (s) => {
      const n = (s.user && (s.user.display_name || s.user.username)) || ''
      return n ? n.slice(0, 1).toUpperCase() : '?'
    },
    roleLabel: (s) => (s.user && s.user.role === 'admin' ? '管理员' : '销售'),
  },
  actions: {
    async fetchStatus() {
      const r = await get('/auth/status')
      if (r && !r.error) {
        this.authEnabled = !!r.auth_enabled
        this.configured = !!r.configured
        this.authenticated = !!r.authenticated
        this.user = r.user || null
      }
      this.ready = true
    },
    async login(username, password) {
      const r = await post('/auth/login', { username, password })
      if (r.error) return r.error
      this.authenticated = true
      this.configured = true
      this.user = r.user || null
      return ''
    },
    async setup(username, password) {
      const r = await post('/auth/setup', { username, password })
      if (r.error) return r.error
      this.authenticated = true
      this.configured = true
      this.user = r.user || null
      return ''
    },
    async change(oldPassword, newPassword) {
      const r = await post('/auth/change', { password: oldPassword, new_password: newPassword })
      return r.error || ''
    },
    async logout() {
      await post('/auth/logout', {})
      this.authenticated = false
      this.user = null
    },
    markUnauthenticated() {
      this.authenticated = false
      this.user = null
    },
  },
})
