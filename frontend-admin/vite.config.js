import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Same proxy shape as the main app: same-origin '/api' in both modes (vite
// dev proxy here, nginx rewrite-strip on admin.arrivalstory.com in prod).
const apiTarget = process.env.API_PROXY_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3001,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
