<template>
  <div class="fb">
    <div class="fb-inner" :class="{ 'is-collapsed': collapsed && hasMore }" @keydown="onKeydown">
      <div class="fb-fields">
        <slot />
      </div>
      <div class="fb-actions">
        <el-button type="primary" :icon="Search" size="default" @click="emit('search')">搜索</el-button>
        <el-button :icon="RefreshLeft" size="default" plain @click="emit('reset')">重置</el-button>
        <slot name="extra" />
        <el-button
          v-if="hasMore"
          text
          size="default"
          class="fb-toggle"
          @click="collapsed = !collapsed"
        >
          {{ collapsed ? '更多筛选' : '收起' }}
          <el-icon class="fb-toggle-icon"><component :is="collapsed ? 'ArrowDown' : 'ArrowUp'" /></el-icon>
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
// 搜索栏：一行紧凑版；宽屏字段自动换行，按钮永远右靠。
import { ref, useSlots, computed } from 'vue'
import { Search, RefreshLeft, ArrowDown, ArrowUp } from '@element-plus/icons-vue'

const emit = defineEmits(['search', 'reset'])
defineProps({ hasMore: { type: Boolean, default: false } })
const collapsed = ref(true)

// 回车即搜索：只在普通文本输入框触发，选择器/日期/数字/只读框交给各自的确认逻辑
function onKeydown(e) {
  if (e.key !== 'Enter') return
  const t = e.target
  if (!t || t.tagName !== 'INPUT' || t.readOnly) return
  if (t.closest('.el-select, .el-autocomplete, .el-input-number, .el-date-editor')) return
  e.preventDefault()
  emit('search')
}
</script>

<style scoped>
.fb {
  background: var(--crm-bg-card);
  border: 1px solid var(--crm-border-soft);
  border-radius: var(--crm-radius-lg);
  padding: 14px 16px;
  margin-bottom: 16px;
  box-shadow: var(--crm-shadow-xs);
}
.fb-inner {
  display: flex; align-items: center; gap: 12px;
  flex-wrap: wrap;
}
.fb-fields {
  display: flex; align-items: center; gap: 10px;
  flex: 1; min-width: 0; flex-wrap: wrap;
}
.fb-fields :deep(.el-form-item) { margin-bottom: 0 !important; margin-right: 0 !important; }
.fb-fields :deep(.el-form-item__label) { padding-right: 6px !important; font-size: 12.5px !important; color: var(--crm-fg-3) !important; }
.fb-fields :deep(.el-input__wrapper),
.fb-fields :deep(.el-select__wrapper) { font-size: 13px; }

.fb-actions { display: flex; align-items: center; gap: 6px; flex-shrink: 0; margin-left: auto; }
.fb-toggle { color: var(--crm-fg-3) !important; font-size: 12.5px !important; padding: 0 6px !important; }
.fb-toggle:hover { color: var(--crm-primary) !important; }
.fb-toggle-icon { margin-left: 2px; }

/* 折叠：只保留前 3 个字段（窄屏更严格），其他隐藏 */
.is-collapsed .fb-fields :deep(.el-form-item:nth-child(n + 4)) { display: none; }
@media (max-width: 900px) { .is-collapsed .fb-fields :deep(.el-form-item:nth-child(n + 2)) { display: none; } }

@media (max-width: 640px) {
  .fb { padding: 10px 12px; }
  .fb-inner { gap: 8px; }
  .fb-actions { width: 100%; margin-left: 0; justify-content: flex-end; }
}
</style>
