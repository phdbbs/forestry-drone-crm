import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 仅用于运行时冒烟测试：把整个应用打成单文件 IIFE，供 jsdom 直接执行
export default defineConfig({
  plugins: [vue()],
  define: { 'process.env.NODE_ENV': '"production"' },
  build: {
    outDir: 'dist-test',
    emptyOutDir: true,
    minify: false,
    cssCodeSplit: false,
    rollupOptions: {
      input: 'src/main.js',
      output: {
        format: 'iife',
        entryFileNames: 'app.iife.js',
        inlineDynamicImports: true,
      },
    },
  },
})
