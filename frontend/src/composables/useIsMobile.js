import { ref } from 'vue'

/**
 * 移动端断点（与 styles/theme.css 里的 @media (max-width: 768px) 保持一致）。
 *
 * 用共享的单例 ref：模块只会被求值一次，因此全局只有一个 resize 监听，
 * 多个组件调用 useIsMobile() 拿到的是同一个响应式值。
 *
 * 什么时候需要它 —— 只在「CSS 表达不了」的时候：
 *   - Element Plus 的 prop 驱动的布局，如 el-descriptions 的 :column、
 *     el-drawer 的 :size、el-table-column 的 :fixed
 * 纯样式问题一律放 theme.css 的媒体查询里，不要往这里加。
 */
const MOBILE_MAX = 768

const isMobile = ref(
  typeof window !== 'undefined' && window.innerWidth <= MOBILE_MAX
)

if (typeof window !== 'undefined') {
  window.addEventListener(
    'resize',
    () => { isMobile.value = window.innerWidth <= MOBILE_MAX },
    { passive: true }
  )
}

export function useIsMobile() {
  return isMobile
}
