<template>
  <div class="sc" :class="{ 'is-clickable': clickable }" @click="clickable && emit('click')">
    <div class="sc-main">
      <div class="sc-label">
        <span>{{ label }}</span>
        <el-tooltip v-if="hint" :content="hint" placement="top">
          <el-icon class="sc-hint" :size="12"><InfoFilled /></el-icon>
        </el-tooltip>
      </div>
      <el-skeleton v-if="loading" animated :rows="1" class="sc-skeleton" />
      <div v-else class="sc-value-row">
        <span class="sc-value" :class="{ 'is-alert': alert }">
          <template v-if="numeric !== null">
            <span class="sc-num">{{ formattedNum }}</span>
            <span v-if="suffix" class="sc-suffix">{{ suffix }}</span>
          </template>
          <template v-else>{{ value }}</template>
        </span>
        <span v-if="delta" class="sc-delta" :class="`sc-delta--${deltaTone}`">
          <el-icon :size="10"><component :is="deltaTone === 'up' ? 'Top' : deltaTone === 'down' ? 'Bottom' : 'Minus'" /></el-icon>
          {{ delta }}
        </span>
      </div>
      <div v-if="footnote" class="sc-foot">{{ footnote }}</div>
    </div>
    <div v-if="icon" class="sc-icon" :class="`sc-icon--${tone}`">
      <el-icon :size="18"><component :is="icon" /></el-icon>
    </div>
  </div>
</template>

<script setup>
// 指标卡：Linear / Vercel dashboard 风格
// - 大数字（tabular-nums，Manrope）
// - 淡色图标（背景为语义色 soft 变体）
// - 支持趋势/说明脚注
import { computed } from 'vue'
import { InfoFilled, Top, Bottom, Minus } from '@element-plus/icons-vue'

const props = defineProps({
  label: String,
  value: [String, Number],
  icon: { type: String, default: '' },
  tone: { type: String, default: 'primary' }, // primary / success / warning / danger / info / neutral
  suffix: { type: String, default: '' },
  precision: { type: Number, default: 0 },
  alert: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  delta: { type: String, default: '' },
  deltaTone: { type: String, default: 'neutral' }, // up / down / neutral
  footnote: { type: String, default: '' },
  hint: { type: String, default: '' },
  clickable: { type: Boolean, default: false },
})
const emit = defineEmits(['click'])

const numeric = computed(() => {
  const v = props.value
  if (v === '' || v === null || v === undefined) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
})
const formattedNum = computed(() => {
  if (numeric.value === null) return ''
  const fixed = numeric.value.toFixed(props.precision)
  // 千分位（仅整数部分）
  const [i, d] = fixed.split('.')
  const ii = i.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return d ? `${ii}.${d}` : ii
})
</script>

<style scoped>
.sc {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;
  background: var(--crm-bg-card);
  border: 1px solid var(--crm-border-soft);
  border-radius: var(--crm-radius-lg);
  padding: 18px 20px;
  box-shadow: var(--crm-shadow-xs);
  transition: border-color var(--crm-dur-fast) var(--crm-ease-out), box-shadow var(--crm-dur-fast) var(--crm-ease-out), transform var(--crm-dur-fast) var(--crm-ease-out);
  height: 100%;
}
.sc.is-clickable { cursor: pointer; }
.sc.is-clickable:hover {
  border-color: var(--crm-pine-200);
  box-shadow: var(--crm-shadow-sm);
  transform: translateY(-1px);
}
.sc-main { min-width: 0; flex: 1; }
.sc-label {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 12.5px; color: var(--crm-fg-3); font-weight: 500;
  letter-spacing: -0.005em;
}
.sc-hint { color: var(--crm-fg-4); cursor: help; }
.sc-value-row { display: flex; align-items: baseline; gap: 8px; margin-top: 6px; flex-wrap: wrap; }
.sc-value {
  font-family: var(--crm-font-display);
  font-variant-numeric: tabular-nums;
  font-size: 26px; font-weight: 700; letter-spacing: -0.028em;
  color: var(--crm-fg-1); line-height: 1.1;
}
.sc-value.is-alert { color: var(--crm-rose-500); }
.sc-num { font-family: var(--crm-font-display); }
.sc-suffix { font-size: 14px; font-weight: 500; color: var(--crm-fg-3); margin-left: 2px; }
.sc-delta {
  display: inline-flex; align-items: center; gap: 1px;
  font-size: 11.5px; font-weight: 600;
  padding: 2px 6px; border-radius: var(--crm-radius-sm);
  font-family: var(--crm-font-mono);
  letter-spacing: -0.02em;
}
.sc-delta--up { background: var(--crm-pine-25); color: var(--crm-pine-600); }
.sc-delta--down { background: var(--crm-rose-50); color: var(--crm-rose-500); }
.sc-delta--neutral { background: var(--crm-slate-100); color: var(--crm-fg-3); }
.sc-foot { margin-top: 4px; font-size: 11.5px; color: var(--crm-fg-4); }
.sc-skeleton { width: 88px; margin-top: 8px; }
.sc-icon {
  width: 36px; height: 36px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  border: 1px solid transparent;
}
.sc-icon--primary { background: var(--crm-pine-25); color: var(--crm-pine-600); border-color: var(--crm-pine-50); }
.sc-icon--success { background: var(--crm-pine-25); color: var(--crm-pine-600); border-color: var(--crm-pine-50); }
.sc-icon--warning { background: var(--crm-amber-50); color: var(--crm-amber-500); border-color: #f5dfb8; }
.sc-icon--danger  { background: var(--crm-rose-50); color: var(--crm-rose-500); border-color: #f2cccc; }
.sc-icon--info    { background: var(--crm-sky-50); color: var(--crm-sky-500); border-color: #cae1f1; }
.sc-icon--neutral { background: var(--crm-slate-100); color: var(--crm-fg-2); border-color: var(--crm-slate-200); }
</style>
