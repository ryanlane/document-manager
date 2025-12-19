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
      // Use clientPort to handle port mapping (3001 -> 3000)
      clientPort: process.env.VITE_HMR_PORT ? parseInt(process.env.VITE_HMR_PORT) : undefined
    },
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://api:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
        timeout: 60000,
        proxyTimeout: 60000
      }
    }
  }
})
