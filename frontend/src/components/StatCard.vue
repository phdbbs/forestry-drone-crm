<template>
  <el-card shadow="never" body-style="padding:0">
    <div class="stat-card">
      <div class="stat-icon" :style="{ background: color }">
        <el-icon :size="24"><component :is="icon" /></el-icon>
      </div>
      <div>
        <div class="stat-num" :style="{ color: valueColor }">{{ value }}</div>
        <div class="stat-label">{{ label }}</div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
defineProps({
  label: String,
  value: [String, Number],
  icon: { type: String, default: 'Aim' },
  color: { type: String, default: 'var(--el-color-primary)' },
  valueColor: { type: String, default: '#1f2d24' },
})
</script>
