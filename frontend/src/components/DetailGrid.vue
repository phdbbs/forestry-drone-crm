<template>
  <div class="detail-grid">
    <template v-for="(it, i) in items" :key="i">
      <div :class="['dg-item', it.full ? 'full' : '']">
        <span class="dg-label">{{ it.label }}：</span>
        <slot v-if="it.slot" :name="it.slot" :item="it" />
        <template v-else>{{ it.value || (it.value === 0 ? 0 : '-') }}</template>
      </div>
    </template>
  </div>
</template>

<script setup>
// 详情弹窗字段网格：items=[{label, value, full, slot}]
defineProps({ items: { type: Array, default: () => [] } })
</script>
