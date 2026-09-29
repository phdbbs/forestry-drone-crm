<template>
  <div class="pt">
    <el-table
      ref="tableRef"
      :data="paged"
      v-loading="loading"
      :default-sort="defaultSort"
      @sort-change="onSortChange"
      @header-dragend="onDragend"
      :row-class-name="rowClassName || ''"
      :size="size"
      border
      class="pt-table"
      :empty-text="''"
    >
      <slot />
      <template #empty>
        <div class="pt-empty">
          <div class="pt-empty-icon">
            <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="6" width="18" height="14" rx="2"/>
              <path d="M8 3v3M16 3v3M3 11h18"/>
            </svg>
          </div>
          <div class="pt-empty-text">{{ emptyText || '暂无数据' }}</div>
          <div v-if="emptyHint" class="pt-empty-hint">{{ emptyHint }}</div>
          <slot name="empty-action" />
        </div>
      </template>
    </el-table>
    <div v-if="showFooter" class="pt-footer">
      <div class="pt-count">
        <span class="pt-count-num">{{ sorted.length }}</span>
        <span class="pt-count-label">条记录</span>
        <span v-if="sorted.length" class="pt-count-range">
          · 当前 {{ (page - 1) * pageSize + 1 }}–{{ Math.min(page * pageSize, sorted.length) }}
        </span>
      </div>
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="sorted.length"
        :page-sizes="[10, 20, 50, 100]"
        layout="sizes, prev, pager, next, jumper"
        size="small"
        background
      />
    </div>
  </div>
</template>

<script setup>
// 通用表格：全量数据传入；内部负责排序（跨页）+ 分页 + 列宽拖拽记忆。
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import Sortable from 'sortablejs'

const props = defineProps({
  data: { type: Array, default: () => [] },
  storageKey: { type: String, required: true },
  pageSize: { type: Number, default: 20 },
  loading: { type: Boolean, default: false },
  defaultSort: { type: Object, default: () => ({ prop: '', order: '' }) },
  size: { type: String, default: 'default' },
  emptyText: { type: String, default: '' },
  emptyHint: { type: String, default: '' },
  showFooter: { type: Boolean, default: true },
  rowClassName: { type: [String, Function], default: '' },
  reorderable: { type: Boolean, default: true },
})
const tableRef = ref(null)
const page = ref(1)
const pageSize = ref(props.pageSize)
const sortProp = ref(props.defaultSort.prop || '')
const sortOrder = ref(props.defaultSort.order === 'ascending' ? 1 : -1)

const WKEY = 'crm_v2_widths_' + props.storageKey

const sorted = computed(() => {
  if (!sortProp.value) return props.data
  const key = sortProp.value, dir = sortOrder.value
  return [...props.data].sort((a, b) => {
    let va = a[key], vb = b[key]
    if (va == null) va = ''
    if (vb == null) vb = ''
    // 日期统一归一化比较：ISO(2026-09-25 / 带时间) 与 MM-DD-YY(09-28-26) 两种展示格式，
    // 避免 parseFloat 把 "2026-09-25" 截成 2026、把 "09-28-26" 截成 9 导致同年/同月排序失效
    const isoPat = /^(\d{4})-(\d{2})-(\d{2})([ T](\d{2}):(\d{2}))?$/
    const mdyPat = /^(\d{2})-(\d{2})-(\d{2})$/
    const norm = (x) => {
      const s = String(x).trim()
      let m = isoPat.exec(s)
      if (m) return `${m[1]}${m[2]}${m[3]}${m[5] || '00'}${m[6] || '00'}`
      m = mdyPat.exec(s)
      if (m) return `20${m[3]}${m[1]}${m[2]}`
      return null
    }
    const sa0 = String(va).trim(), sb0 = String(vb).trim()
    const na0 = norm(sa0), nb0 = norm(sb0)
    if (na0 !== null && nb0 !== null) {
      return (na0 < nb0 ? -1 : na0 > nb0 ? 1 : 0) * dir
    }
    const sa = sa0, sb = sb0
    const na = parseFloat(va), nb = parseFloat(vb)
    if (!isNaN(na) && !isNaN(nb) && sa !== '' && sb !== '' && /^[\d.\-+]/.test(sa) && /^[\d.\-+]/.test(sb) && !/^\d{1,2}-\d{1,2}/.test(sa)) {
      return (na - nb) * dir
    }
    return sa.localeCompare(sb, 'zh') * dir
  })
})
const paged = computed(() => sorted.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))

watch(() => props.data.length, () => {
  const maxPage = Math.max(1, Math.ceil(sorted.value.length / pageSize.value))
  if (page.value > maxPage) page.value = maxPage
})

function onSortChange({ prop, order }) {
  if (!order) { sortProp.value = ''; return }
  sortProp.value = prop
  sortOrder.value = order === 'ascending' ? 1 : -1
  page.value = 1
}
function loadWidths() { try { return JSON.parse(localStorage.getItem(WKEY)) || {} } catch (e) { return {} } }
function applyWidths() {
  const saved = loadWidths()
  if (!Object.keys(saved).length) return
  // 作用于源数组 _columns，保证重排/重算后仍按 property/label 命中记忆宽度
  const cols = tableRef.value?.store?.states?._columns?.value || []
  cols.forEach((col) => {
    if (col.resizable === false) return
    const k = colKey(col)
    if (k && saved[k]) { col.width = saved[k]; col.realWidth = saved[k] }
  })
  tableRef.value?.doLayout()
}
function onDragend(newWidth, _old, column) {
  const saved = loadWidths()
  const k = colKey(column)
  if (k) {
    saved[k] = newWidth
    localStorage.setItem(WKEY, JSON.stringify(saved))
    // 同步源列对象，避免后续 updateColumns 用旧 width 覆盖
    if (column) { column.width = newWidth; column.realWidth = newWidth }
  }
}

// ---- #4 列顺序拖拽：借 Sortable 作用于表头行，同步 Element Plus 内部列数组 ----
const OKEY = 'crm_v2_order_' + props.storageKey
const sortableRef = ref(null)
// 表头右边缘「改列宽」热区宽度（px）；Sortable 在该区间内让路给改宽
const RESIZE_ZONE = 10
const MIN_COL_W = 48

function storeCols() {
  const st = tableRef.value?.store
  return st?.states?._columns?.value || null
}
function colKey(c) {
  return c.property || c.label || (c.type ? 'type:' + c.type : 'id:' + c.id)
}
function recompute() {
  const st = tableRef.value?.store
  try { st?.updateColumns?.() } catch (e) { /* 兼容不同版本内部实现 */ }
  tableRef.value?.doLayout?.()
}
function persistOrder() {
  const cols = storeCols()
  if (!cols) return
  const keys = cols.map(colKey)
  localStorage.setItem(OKEY, JSON.stringify(keys))
}
function applyOrder() {
  const cols = storeCols()
  if (!cols) return
  let order
  try { order = JSON.parse(localStorage.getItem(OKEY)) } catch (e) { order = null }
  if (!Array.isArray(order) || !order.length) return
  const map = {}
  cols.forEach((c) => { map[colKey(c)] = c })
  const ordered = order.map((k) => map[k]).filter(Boolean)
  const rest = cols.filter((c) => !order.includes(colKey(c)))
  const next = [...ordered, ...rest]
  if (next.length === cols.length && next.every((c, i) => c === cols[i])) return
  tableRef.value.store.states._columns.value = next
  recompute()
}
function setupReorder() {
  destroySortable()
  const el = tableRef.value?.$el?.querySelector('.el-table__header-wrapper tr')
  if (!el) return
  sortableRef.value = Sortable.create(el, {
    animation: 150,
    delay: 0,
    // 命中的是「调宽热区」时不要 preventDefault，否则会顺带掐掉列宽拖拽
    preventOnFilter: false,
    // 展开/选择等无业务含义的控制列不参与拖拽，避免用户误拖
    filter: (evt) => {
      const th = evt.target?.closest?.('th')
      if (!th) return false
      // 靠近右侧分隔线（列宽调宽热区）时不启动重排，把这条边让给改列宽
      const rect = th.getBoundingClientRect()
      const x = evt.clientX != null ? evt.clientX : (evt.touches && evt.touches[0] && evt.touches[0].clientX)
      if (x != null && rect.right - x <= RESIZE_ZONE && rect.right - x >= 0) return true
      const idx = Array.prototype.indexOf.call(el.children, th)
      const cols = storeCols() || []
      const c = cols[idx]
      return !!(c && (c.type === 'expand' || c.type === 'selection'))
    },
    onEnd({ oldIndex, newIndex }) {
      if (oldIndex === newIndex) return
      const cols = storeCols()
      if (!cols) return
      const next = cols.slice()
      const [moved] = next.splice(oldIndex, 1)
      next.splice(newIndex, 0, moved)
      tableRef.value.store.states._columns.value = next
      persistOrder()
      recompute()
      applyWidths()
      // updateColumns 可能重建表头 <tr>，需重新绑定拖拽
      nextTick(() => setupReorder())
    },
  })
}
function destroySortable() {
  try { sortableRef.value?.destroy?.() } catch (e) { /* noop */ }
  sortableRef.value = null
}

// ---- 双击列分隔线/表头 → 自动适配本列内容完整显示的最小宽度 ----
let _measureCtx = null
function fontOf(node) {
  const cs = getComputedStyle(node)
  return `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`
}
function textWidth(node) {
  if (!node) return 0
  const txt = (node.innerText || node.textContent || '').replace(/\s+/g, ' ').trim()
  if (!txt) return 0
  if (!_measureCtx) _measureCtx = document.createElement('canvas').getContext('2d')
  _measureCtx.font = fontOf(node)
  return _measureCtx.measureText(txt).width
}
function autoFitByIndex(idx) {
  const table = tableRef.value
  if (!table) return
  const el = table.$el
  const cols = storeCols()
  const col = cols && cols[idx]
  if (!col || col.resizable === false) return
  const headerCell = el.querySelector(`.el-table__header-wrapper tr:first-child th:nth-child(${idx + 1})`)
  if (!headerCell) return
  const hcell = headerCell.querySelector('.cell') || headerCell
  let need = textWidth(hcell)
  if (headerCell.querySelector('.caret-wrapper')) need += 24 // 排序箭头留位
  const bodyRows = el.querySelectorAll('.el-table__body-wrapper tbody tr')
  bodyRows.forEach((tr) => {
    const td = tr.children[idx]
    if (!td) return
    const c = td.querySelector('.cell') || td
    const w = textWidth(c)
    if (w > need) need = w
  })
  need += 26 // .cell 左右内边距 + 边框
  need = Math.max(56, Math.min(Math.ceil(need), 720))
  col.width = need
  col.realWidth = need
  const saved = loadWidths()
  saved[colKey(col)] = need
  localStorage.setItem(WKEY, JSON.stringify(saved))
  recompute()
}
let headerElForFit = null
function onHeaderDblclick(e) {
  const th = e.target && e.target.closest ? e.target.closest('th') : null
  if (!th) return
  const row = th.parentElement
  if (!row) return
  const idx = Array.prototype.indexOf.call(row.children, th)
  if (idx < 0) return
  autoFitByIndex(idx)
}
function setupAutoFit() {
  const el = tableRef.value?.$el?.querySelector('.el-table__header-wrapper')
  if (!el) return
  headerElForFit = el
  el.addEventListener('dblclick', onHeaderDblclick)
}
function teardownAutoFit() {
  try { headerElForFit && headerElForFit.removeEventListener('dblclick', onHeaderDblclick) } catch (e) { /* noop */ }
  headerElForFit = null
}

// ---- 自定义「拖动列边线改列宽」：完全接管，避免与整行拖拽重排冲突 ----
// 之前依赖 Element Plus 原生 resize（只在距 th 右缘 8px 内生效），
// 但那 8px 又被 Sortable 的整表头拖拽挤压，导致「边线难选、选了拖不动」。
// 这里用一个更宽（RESIZE_ZONE）且带高亮提示的自建热区：
//   pointermove（捕获）→ 命中右缘时给该 th 加高亮类 + col-resize 光标；
//   pointerdown（捕获）→ 命中即在捕获阶段 stopPropagation，抢在 Sortable / EP 之前，
//                        然后自己按 delta 实时改列宽，松手时持久化。
let _resizeEl = null
let _resize = null // { col, startX, startW, key }
function headerWrapEl() {
  return tableRef.value?.$el?.querySelector('.el-table__header-wrapper') || null
}
function firstRowThs() {
  const el = headerWrapEl()
  return el ? Array.from(el.querySelectorAll('tr:first-child > th')) : []
}
// 返回指针命中的「可改宽」th（其右缘 RESIZE_ZONE 内），否则 null
function resizeThAt(clientX, clientY) {
  const ths = firstRowThs()
  for (const th of ths) {
    const r = th.getBoundingClientRect()
    if (clientY < r.top || clientY > r.bottom) continue
    const d = r.right - clientX
    if (d >= 0 && d <= RESIZE_ZONE && r.width > MIN_COL_W + 8) return th
  }
  return null
}
function clearHot() {
  firstRowThs().forEach((th) => {
    th.classList.remove('is-resize-hot')
    const c = th.querySelector('.cell')
    if (c) c.style.cursor = ''
  })
}
function onResizeHover(e) {
  if (_resize) return
  const th = resizeThAt(e.clientX, e.clientY)
  clearHot()
  if (!th) return
  th.classList.add('is-resize-hot')
  const c = th.querySelector('.cell')
  if (c) c.style.cursor = 'col-resize'
}
function colIndexOfTh(th) {
  const row = th.parentElement
  if (!row) return -1
  return Array.prototype.indexOf.call(row.children, th)
}
function onResizeDownCapture(e) {
  if (e.button !== 0) return
  const th = resizeThAt(e.clientX, e.clientY)
  if (!th) return
  const idx = colIndexOfTh(th)
  const cols = storeCols() || []
  const col = cols[idx]
  if (!col || col.resizable === false) return
  // 抢在 Sortable(tr, 冒泡) 与 Element Plus(th) 之前接管
  e.preventDefault()
  e.stopPropagation()
  const r = th.getBoundingClientRect()
  const startW = Math.round(Number(col.realWidth || col.width || r.width))
  _resize = { col, startX: e.clientX, startW, key: colKey(col) }
  document.addEventListener('pointermove', onResizeMove)
  document.addEventListener('pointerup', onResizeUp)
}
function onResizeMove(e) {
  if (!_resize) return
  const delta = e.clientX - _resize.startX
  let w = Math.round(_resize.startW + delta)
  w = Math.max(MIN_COL_W, Math.min(3000, w))
  _resize.col.width = w
  _resize.col.realWidth = w
  tableRef.value?.doLayout?.()
}
function onResizeUp() {
  document.removeEventListener('pointermove', onResizeMove)
  document.removeEventListener('pointerup', onResizeUp)
  if (_resize && _resize.col) {
    const w = Math.round(Number(_resize.col.realWidth || _resize.col.width))
    if (_resize.key) {
      const saved = loadWidths()
      saved[_resize.key] = w
      localStorage.setItem(WKEY, JSON.stringify(saved))
    }
  }
  _resize = null
}
function setupResize() {
  const el = headerWrapEl()
  if (!el) return
  _resizeEl = el
  el.addEventListener('pointermove', onResizeHover)
  el.addEventListener('pointerdown', onResizeDownCapture, true) // 捕获
}
function teardownResize() {
  if (_resizeEl) {
    _resizeEl.removeEventListener('pointermove', onResizeHover)
    _resizeEl.removeEventListener('pointerdown', onResizeDownCapture, true)
  }
  _resizeEl = null
  document.removeEventListener('pointermove', onResizeMove)
  document.removeEventListener('pointerup', onResizeUp)
}

// el-table-column 在各自 mounted 才注册进 store；轮询直到列就绪再恢复顺序/宽度，
// 否则刷新时 applyOrder 会对着空数组跑一遍，导致保存的顺序不生效。
function whenColumnsReady(cb) {
  let tries = 0
  const tick = () => {
    const cols = storeCols()
    if ((cols && cols.length) || tries > 30) { cb(); return }
    tries += 1
    requestAnimationFrame(tick)
  }
  requestAnimationFrame(tick)
}

onMounted(() => {
  whenColumnsReady(() => {
    applyOrder()
    applyWidths()
    setupAutoFit()
    setupResize()
    if (props.reorderable && window.innerWidth > 900) setupReorder()
  })
})
onBeforeUnmount(() => {
  destroySortable()
  teardownAutoFit()
  teardownResize()
})
</script>

<style scoped>
.pt { background: var(--crm-bg-card); border-radius: var(--crm-radius-lg); overflow: hidden; }
.pt-table { background: transparent !important; }
.pt-table :deep(.el-table__inner-wrapper::before) { display: none; } /* 去掉底部横线 */
.pt-table :deep(.el-table__header th .cell) { cursor: grab; }
.pt-table :deep(.el-table__header th:active .cell) { cursor: grabbing; }
/* 自定义改列宽高亮：悬停到某列表头右缘时，光标变 col-resize 并高亮这条竖线 */
.pt-table :deep(.el-table__header th) { position: relative; }
.pt-table :deep(.el-table__header th.is-resize-hot),
.pt-table :deep(.el-table__header th.is-resize-hot .cell) { cursor: col-resize; }
.pt-table :deep(.el-table__header th.is-resize-hot)::after {
  content: ''; position: absolute; top: 6px; bottom: 6px; right: 0; width: 2px;
  background: var(--crm-pine-500, var(--crm-primary, #136a47)); border-radius: 2px; pointer-events: none;
}

/* 内容不足列宽时不折行：超出隐藏、能显示多少显示多少；含表头。
   EP 默认 .cell 是 white-space:normal + overflow-wrap:break-word，
   会把长编号 / 日期 / 电话 / 金额从中间挤到第二行。
   注意：`:deep(.el-table .cell)` 会编译成「后代」选择器 `.pt-table[data-v] .el-table .cell`，
   但 .pt-table 与 .el-table 在同一个根元素上（没有后代 .el-table），导致规则永不命中、
   body 单元格一直在折行。改为直接命中后代 .cell（表头/表体都覆盖）。
   white-space:nowrap 不会把块级子元素并到一行，所以「主标题 + cell-meta」双行排版保留，
   只是每一行内部不再换行。 */
.pt-table :deep(.cell),
.pt-table :deep(.cell *) {
  white-space: nowrap !important;
  word-break: normal !important;
  overflow-wrap: normal !important;
}
.pt-table :deep(.cell) {
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 空态 */
.pt-empty { padding: 56px 20px; text-align: center; color: var(--crm-fg-3); }
.pt-empty-icon {
  width: 56px; height: 56px; margin: 0 auto 12px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 16px; background: var(--crm-slate-100); color: var(--crm-slate-400);
}
.pt-empty-text { font-size: 13.5px; color: var(--crm-fg-2); font-weight: 500; }
.pt-empty-hint { margin-top: 4px; font-size: 12px; color: var(--crm-fg-4); }

/* 页脚 */
.pt-footer {
  display: flex; align-items: center; justify-content: space-between;
  gap: 16px; padding: 12px 20px;
  border-top: 1px solid var(--crm-border-soft);
  background: var(--crm-slate-25);
  flex-wrap: wrap;
}
.pt-count { font-size: 12.5px; color: var(--crm-fg-3); }
.pt-count-num { font-family: var(--crm-font-mono); font-weight: 600; color: var(--crm-fg-1); margin-right: 4px; }
.pt-count-range { color: var(--crm-fg-4); font-family: var(--crm-font-mono); font-size: 11.5px; }
@media (max-width: 640px) {
  .pt-footer { padding: 10px 12px; }
  .pt-count { font-size: 11.5px; }
}
</style>
