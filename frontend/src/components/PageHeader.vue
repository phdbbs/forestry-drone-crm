<template>
  <div class="pc-header">
    <div class="pc-title-wrap">
      <div class="pc-title-row">
        <h1 class="pc-title">{{ title }}</h1>
        <el-tag v-if="tag" size="small" :type="tagType" effect="plain" class="pc-tag">{{ tag }}</el-tag>
        <slot name="title-extra" />
      </div>
      <div v-if="subtitle" class="pc-sub">{{ subtitle }}</div>
    </div>
    <div class="pc-actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
// 页面顶部标题条：统一"标题 + 副标题 + 操作按钮"版式。
// 各视图不再各自写 page-header flex 布局，视觉节奏一次到位。
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  tag: { type: String, default: '' },
  tagType: { type: String, default: 'info' },
})
</script>

<style scoped>
.pc-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 20px; margin-bottom: 20px; flex-wrap: wrap;
}
.pc-title-wrap { min-width: 0; flex: 1; }
.pc-title-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.pc-title {
  font-family: var(--crm-font-display);
  font-size: 22px; font-weight: 600; letter-spacing: -0.02em;
  color: var(--crm-fg-1); margin: 0; line-height: 1.25;
}
.pc-tag { font-size: 11px !important; }
.pc-sub {
  font-size: 13px; color: var(--crm-fg-3); margin-top: 4px;
  line-height: 1.5;
}
.pc-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; flex-shrink: 0; }
@media (max-width: 768px) {
  .pc-title { font-size: 18px; }
  .pc-header { margin-bottom: 16px; }
}
</style>
