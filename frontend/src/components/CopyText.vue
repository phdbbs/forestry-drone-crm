<template>
  <span v-if="value" class="copy-text" :class="{ 'is-tel': tel }">
    <a v-if="tel" :href="'tel:' + value" class="ct-val">{{ label || value }}</a>
    <span v-else class="ct-val">{{ label || value }}</span>
    <el-icon class="ct-copy" title="复制" @click.stop="copy"><CopyDocument /></el-icon>
    <teleport to="body">
      <transition name="ct-fade">
        <span v-if="copied" class="ct-toast">已复制</span>
      </transition>
    </teleport>
  </span>
  <span v-else class="muted">{{ placeholder }}</span>
</template>

<script setup>
// 一键复制 + 可选 tel: 拨号。用于电话/地址/流水号等高频复制字段。
import { ref } from 'vue'
import { CopyDocument } from '@element-plus/icons-vue'

const props = defineProps({
  value: { type: String, default: '' },
  label: { type: String, default: '' },
  tel: { type: Boolean, default: false },
  placeholder: { type: String, default: '-' },
})
const copied = ref(false)
let timer = null
async function copy() {
  try {
    await navigator.clipboard.writeText(props.value)
  } catch (e) {
    // 剪贴板 API 不可用时降级
    const ta = document.createElement('textarea')
    ta.value = props.value
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    ta.remove()
  }
  copied.value = true
  clearTimeout(timer)
  timer = setTimeout(() => (copied.value = false), 1200)
}
</script>

<style>
.copy-text { display: inline-flex; align-items: center; gap: 3px; }
.copy-text .ct-copy {
  opacity: 0; cursor: pointer; color: var(--crm-slate-400, #a3adba);
  transition: opacity 120ms ease-out, color 120ms;
  font-size: 13px;
}
.copy-text:hover .ct-copy { opacity: 1; }
.copy-text .ct-copy:hover { color: var(--crm-pine-500, #136a47); }
.copy-text.is-tel .ct-val { color: var(--crm-pine-500, #136a47); text-decoration: none; }
.copy-text.is-tel .ct-val:hover { text-decoration: underline; }
.ct-toast {
  position: fixed; z-index: 9999; pointer-events: none;
  background: var(--crm-slate-800, #232935); color: #fff; font-size: 12px;
  padding: 4px 10px; border-radius: 6px;
}
.ct-fade-enter-active, .ct-fade-leave-active { transition: opacity 120ms; }
.ct-fade-enter-from, .ct-fade-leave-to { opacity: 0; }
</style>
