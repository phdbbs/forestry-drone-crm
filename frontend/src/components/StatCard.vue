<template>
  <el-card shadow="never" class="stat-card">
    <div class="stat-row">
      <div class="stat-main">
        <div class="stat-label">{{ label }}</div>
        <el-skeleton v-if="loading" animated :rows="1" class="stat-skeleton" />
        <el-statistic
          v-else-if="numeric !== null"
          class="stat-value"
          :value="numeric"
          :precision="precision"
          :suffix="suffix"
          :value-style="valueStyle"
        />
        <div v-else class="stat-value" :class="{ 'is-alert': alert }">{{ value }}</div>
      </div>
      <div class="stat-icon" :class="`stat-icon--${tone}`">
        <el-icon :size="20"><component :is="icon" /></el-icon>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'

// 统计卡：淡色图标 + el-statistic 数值，替代原型期的「实心彩色块 + 手写数字」
const props = defineProps({
  label: String,
  value: [String, Number],
  icon: { type: String, default: 'Aim' },
  // 语义色调，对应 Element Plus 的 primary/success/warning/danger/info
  tone: { type: String, default: 'primary' },
  suffix: { type: String, default: '' },
  precision: { type: Number, default: 0 },
  // 数值用警示色强调（如「紧急线索」）
  alert: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
})

const numeric = computed(() => {
  const v = props.value
  if (v === '' || v === null || v === undefined) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
})

const valueStyle = computed(() => ({
  fontSize: '26px',
  fontWeight: 600,
  lineHeight: 1.15,
  color: props.alert ? 'var(--el-color-danger)' : 'var(--el-text-color-primary)',
}))
</script>

<style scoped>
.stat-card :deep(.el-card__body) { padding: 18px 20px; }
.stat-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.stat-main { min-width: 0; }
.stat-label { color: var(--el-text-color-secondary); font-size: 13px; margin-bottom: 6px; }
.stat-value { font-variant-numeric: tabular-nums; }
.stat-value.is-alert { color: var(--el-color-danger); }
.stat-skeleton { width: 80px; }
.stat-icon {
  width: 44px; height: 44px; border-radius: var(--el-border-radius-base);
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.stat-icon--primary { background: var(--el-color-primary-light-9); color: var(--el-color-primary); }
.stat-icon--success { background: var(--el-color-success-light-9); color: var(--el-color-success); }
.stat-icon--warning { background: var(--el-color-warning-light-9); color: var(--el-color-warning); }
.stat-icon--danger  { background: var(--el-color-danger-light-9);  color: var(--el-color-danger); }
.stat-icon--info    { background: var(--el-color-info-light-9);    color: var(--el-color-info); }
</style>
