import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 构建产物输出到后端 static/dist，由 Flask 直接托管
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../app/static/dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:5001',
    },
  },
})
