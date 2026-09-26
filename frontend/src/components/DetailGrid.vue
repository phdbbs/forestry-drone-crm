<template>
  <!--
    详情去格线版：把 "label : value" 从 el-descriptions 的重表格里解放出来。
    items = [{ label, value, full, slot, mono, tone }]
      - full=true 独占整行；slot 走具名插槽；mono 用等宽字；tone 语义色
    两列响应式：窄屏退化一列，标签在值上方。
  -->
  <dl class="dg" :class="{ 'dg--bordered': bordered, 'dg--dense': dense }">
    <div
      v-for="(it, i) in normalized"
      :key="i"
      class="dg-row"
      :class="{ 'dg-row--full': it.full }"
    >
      <dt class="dg-label">{{ it.label }}</dt>
      <dd class="dg-value" :class="{ 'is-mono': it.mono, 'is-empty': it._empty, [`is-${it.tone}`]: it.tone }">
        <slot v-if="it.slot" :name="it.slot" :item="it" />
        <template v-else>{{ it._empty ? '—' : it.value }}</template>
      </dd>
    </div>
  </dl>
</template>

<script setup>
import { computed } from 'vue'
import { useIsMobile } from '../composables/useIsMobile'

const props = defineProps({
  items: { type: Array, default: () => [] },
  bordered: { type: Boolean, default: false },
  dense: { type: Boolean, default: false },
})
const isMobile = useIsMobile()
const normalized = computed(() => props.items.map((it) => {
  const v = it.value
  const empty = v === null || v === undefined || v === '' || (typeof v === 'string' && v.trim() === '')
  return { ...it, _empty: empty }
}))
</script>

<style scoped>
.dg {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0;
  margin: 0;
  font-size: 13.5px;
}
.dg--dense { font-size: 13px; }
.dg-row {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  align-items: baseline;
  gap: 12px;
  padding: 9px 0;
  min-width: 0;
}
.dg-row--full { grid-column: 1 / -1; }
.dg--bordered .dg-row {
  border-bottom: 1px solid var(--crm-border-soft);
}
.dg--bordered .dg-row:last-child { border-bottom: none; }
.dg-label {
  color: var(--crm-fg-3);
  font-weight: 400;
  font-size: 12.5px;
  line-height: 1.6;
  letter-spacing: -0.005em;
}
.dg-value {
  color: var(--crm-fg-1);
  margin: 0;
  word-break: break-word;
  overflow-wrap: anywhere;
  line-height: 1.65;
  font-weight: 500;
}
.dg-value.is-empty { color: var(--crm-fg-4); font-weight: 400; }
.dg-value.is-mono { font-family: var(--crm-font-mono); font-variant-numeric: tabular-nums; letter-spacing: -0.01em; }
.dg-value.is-warning { color: var(--crm-amber-500); }
.dg-value.is-danger { color: var(--crm-rose-500); }
.dg-value.is-success { color: var(--crm-pine-600); }
.dg-value.is-primary { color: var(--crm-primary); }

@media (max-width: 900px) {
  .dg { grid-template-columns: 1fr; }
  .dg-row { grid-template-columns: 88px minmax(0, 1fr); padding: 7px 0; }
}
@media (max-width: 560px) {
  .dg-row { grid-template-columns: 1fr; gap: 2px; padding: 10px 0; }
  .dg-label { font-size: 11.5px; }
}
</style>
