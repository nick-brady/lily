import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Inside compose the backend is reachable by service name; when running vite
// on bare metal, point API_PROXY_TARGET at wherever the backend listens.
const apiTarget = process.env.API_PROXY_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // Same-origin API (and SSE) for the browser; the backend keeps no
      // published host port. http-proxy streams SSE responses unbuffered.
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
