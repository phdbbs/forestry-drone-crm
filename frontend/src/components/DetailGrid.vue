<template>
  <el-descriptions
    :column="cols"
    :border="border"
    :label-width="labW"
    size="default"
    class="detail-desc"
  >
    <el-descriptions-item
      v-for="(it, i) in items"
      :key="i"
      :label="it.label"
      :span="it.full ? cols : 1"
    >
      <slot v-if="it.slot" :name="it.slot" :item="it" />
      <span v-else class="dg-value">{{ it.value || (it.value === 0 ? 0 : '-') }}</span>
    </el-descriptions-item>
  </el-descriptions>
</template>

<script setup>
// 详情字段展示：基于 el-descriptions 封装（替代原先手写的 grid）。
// items = [{ label, value, full, slot }]，full=true 时该字段占满整行。
// 具名插槽按 item.slot 转发，用法与旧版一致：<template #serial>...</template>
//
// 窄屏降为单列：两列时每列仅约 180px，减去 label 就放不下内容。
// 这是 prop 驱动的布局，CSS 改不了，只能走 useIsMobile。
import { computed } from 'vue'
import { useIsMobile } from '../composables/useIsMobile'

const props = defineProps({
  items: { type: Array, default: () => [] },
  column: { type: Number, default: 2 },
  border: { type: Boolean, default: true },
  labelWidth: { type: [String, Number], default: 108 },
})

const isMobile = useIsMobile()
const cols = computed(() => (isMobile.value ? 1 : props.column))
const labW = computed(() => (isMobile.value ? 84 : props.labelWidth))
</script>

<style scoped>
.detail-desc :deep(.el-descriptions__label) {
  color: var(--el-text-color-secondary);
  font-weight: 400;
}
.dg-value {
  word-break: break-all;
}
</style>
