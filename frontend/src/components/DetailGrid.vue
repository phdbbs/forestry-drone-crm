<template>
  <el-descriptions
    :column="column"
    :border="border"
    :label-width="labelWidth"
    size="default"
    class="detail-desc"
  >
    <el-descriptions-item
      v-for="(it, i) in items"
      :key="i"
      :label="it.label"
      :span="it.full ? column : 1"
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
defineProps({
  items: { type: Array, default: () => [] },
  column: { type: Number, default: 2 },
  border: { type: Boolean, default: true },
  labelWidth: { type: [String, Number], default: 108 },
})
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
