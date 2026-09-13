import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:5001',
    },
  },
  build: {
    outDir: '../app/static/dist',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1600,
  },
})
