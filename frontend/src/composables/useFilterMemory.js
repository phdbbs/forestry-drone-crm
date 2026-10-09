// 列表筛选条件记忆：localStorage 按页面 key 存取 filter 对象
// 用法：const filter = useFilterMemory('leads', { q: '', region: '', from: '', to: '' })
//       draft 变化后 applyFilter() 会写 filter → 自动持久化；进入页面自动恢复
// 返回的就是 filter 本身（全部列表页都按 `filter.q` 直接取用），不要再包一层。
import { reactive, watch } from 'vue'

export function useFilterMemory(key, defaults) {
  const stored = (() => {
    try { return JSON.parse(localStorage.getItem('crm_v2_filter_' + key) || 'null') } catch (e) { return null }
  })()
  const filter = reactive({ ...defaults, ...(stored || {}) })
  watch(filter, (v) => {
    try { localStorage.setItem('crm_v2_filter_' + key, JSON.stringify(v)) } catch (e) {}
  }, { deep: true })
  return filter
}
