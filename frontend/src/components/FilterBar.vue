<template>
  <el-card shadow="never" class="fb-card" body-style="padding:12px 16px 0 16px">
    <el-form inline @submit.prevent="emit('search')" @keyup.enter="emit('search')">
      <slot />
      <el-form-item>
        <el-button type="primary" @click="emit('search')">
          <el-icon><Search /></el-icon>&nbsp;搜索
        </el-button>
        <el-button @click="emit('reset')">
          <el-icon><Refresh /></el-icon>&nbsp;重置
        </el-button>
        <slot name="extra" />
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup>
// 通用搜索栏：文本框回车自动提交；下拉 change 由父组件绑定立即过滤
const emit = defineEmits(['search', 'reset'])
</script>

<style scoped>
.fb-card { margin-bottom: 12px; }
.fb-card :deep(.el-form-item) { margin-bottom: 12px; }
</style>
