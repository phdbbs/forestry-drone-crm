<template>
  <div>
    <el-table
      ref="tableRef"
      :data="paged"
      stripe
      border
      v-loading="loading"
      empty-text="暂无数据"
      :default-sort="defaultSort"
      @sort-change="onSortChange"
      @header-dragend="onDragend"
    >
      <slot />
    </el-table>
    <div class="pt-footer">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="sorted.length"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        background
      />
    </div>
  </div>
</template>

<script setup>
// 通用表格：全量数据传入，内部负责 排序(跨页) + 分页(默认10条) + 列宽拖拽自动保存
import { ref, computed, watch, onMounted, nextTick } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  storageKey: { type: String, required: true },   // 列宽 localStorage key
  pageSize: { type: Number, default: 10 },
  loading: { type: Boolean, default: false },
  defaultSort: { type: Object, default: () => ({ prop: '', order: '' }) }, // {prop:'created_at', order:'descending'}
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
    const na = parseFloat(va), nb = parseFloat(vb)
    if (!isNaN(na) && !isNaN(nb) && String(va).trim() !== '' && String(vb).trim() !== '' && /^[\d.\-+]/.test(String(va)) && /^[\d.\-+]/.test(String(vb))) {
      return (na - nb) * dir
    }
    return String(va).localeCompare(String(vb), 'zh') * dir
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

function loadWidths() {
  try { return JSON.parse(localStorage.getItem(WKEY)) || {} } catch (e) { return {} }
}
function applyWidths() {
  const saved = loadWidths()
  if (!Object.keys(saved).length) return
  const cols = tableRef.value?.store?.states?.columns?.value || []
  cols.forEach((col) => {
    if (col.resizable === false) return
    const k = col.property || col.label
    if (k && saved[k]) {
      col.width = saved[k]
      col.realWidth = saved[k]
    }
  })
  tableRef.value?.doLayout()
}
function onDragend(newWidth, _old, column) {
  const saved = loadWidths()
  const k = column.property || column.label
  if (k) {
    saved[k] = newWidth
    localStorage.setItem(WKEY, JSON.stringify(saved))
  }
}
onMounted(() => nextTick(applyWidths))
</script>

<style scoped>
.pt-footer {
  display: flex; justify-content: flex-end;
  margin-top: 16px; flex-wrap: wrap; gap: 8px;
}
</style>
