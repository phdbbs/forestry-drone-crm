<template>
  <div class="nf-page">
    <div class="nf-card">
      <div class="nf-eyebrow mono">ROUTE NOT FOUND</div>
      <div class="nf-code">404</div>
      <p class="nf-text">抱歉，你访问的页面不存在或已被移除。</p>
      <div class="nf-actions">
        <el-button type="primary" @click="$router.push('/dashboard')">返回工作台</el-button>
        <el-button @click="$router.back()">返回上一页</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
// 路由兜底页：命中 /:pathMatch(.*)* 时渲染，避免白屏
</script>

<style scoped>
.nf-page {
  min-height: calc(100vh - 160px);
  display: flex; align-items: center; justify-content: center;
  padding: 40px 20px;
}
.nf-card { text-align: center; max-width: 420px; }
.nf-eyebrow {
  font-size: 11px; letter-spacing: 0.22em; color: var(--crm-fg-4);
  text-transform: uppercase; margin-bottom: 6px;
}
.nf-code {
  font-family: var(--crm-font-display);
  font-size: 96px; font-weight: 700; line-height: 1;
  letter-spacing: -0.04em;
  background: linear-gradient(180deg, var(--crm-pine-500), var(--crm-pine-300));
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent; color: transparent;
}
.nf-text { margin: 14px 0 24px; font-size: 14px; color: var(--crm-fg-3); line-height: 1.7; }
.nf-actions { display: flex; gap: 10px; justify-content: center; }
</style>
