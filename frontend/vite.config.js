import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 3000,
    // Enable HMR with polling for Docker/WSL
    watch: {
      usePolling: true,
      interval: 1000
    },
    hmr: {
      host: 'localhost',
      port: 3000
    },
    proxy: {
      '/api': {
        target: 'http://api:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
        timeout: 60000,
        proxyTimeout: 60000
      }
    }
  }
})
