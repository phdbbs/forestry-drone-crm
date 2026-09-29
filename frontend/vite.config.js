import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      // 与后端保持一致：CRM_PORT 环境变量（默认 5003）
      '/api': `http://localhost:${process.env.CRM_PORT || 5003}`,
    },
  },
  build: {
    outDir: '../app/static/dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // 大依赖独立分包：业务代码更新时用户无需重新下载框架包
        manualChunks: {
          'element-plus': ['element-plus', '@element-plus/icons-vue'],
          echarts: ['echarts'],
          marked: ['marked', 'dompurify'],
        },
      },
    },
  },
})
