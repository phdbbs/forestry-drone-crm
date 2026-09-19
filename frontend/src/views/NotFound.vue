<template>
  <div class="page">
    <el-result icon="warning" title="404" sub-title="抱歉，你访问的页面不存在或已被移除">
      <template #extra>
        <el-button type="primary" @click="$router.push('/dashboard')">返回工作台</el-button>
        <el-button @click="$router.back()">返回上一页</el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup>
// 路由兜底页：命中 /:pathMatch(.*)* 时渲染，避免白屏
</script>
