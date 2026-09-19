<template>
  <el-card shadow="never" class="fb-card">
    <el-form inline class="fb-form" @submit.prevent="emit('search')" @keyup.enter="emit('search')">
      <slot />
      <el-form-item class="fb-actions">
        <el-button type="primary" :icon="Search" @click="emit('search')">搜索</el-button>
        <el-button :icon="Refresh" @click="emit('reset')">重置</el-button>
        <slot name="extra" />
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup>
// 通用搜索栏：文本框回车自动提交；下拉 change 由父组件绑定立即过滤。
// 按钮统一用 :icon 属性传图标（Element Plus 会自动处理图标与文字的间距），
// 不再用 <el-icon> + &nbsp; 手工拼装。
import { Search, Refresh } from '@element-plus/icons-vue'

const emit = defineEmits(['search', 'reset'])
</script>

<style scoped>
.fb-card { margin-bottom: var(--crm-block-gap); }
.fb-card :deep(.el-card__body) { padding: 16px 16px 0 16px; }
.fb-form :deep(.el-form-item) { margin-bottom: 16px; }
.fb-actions { margin-right: 0 !important; }
</style>
