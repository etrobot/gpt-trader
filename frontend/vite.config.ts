import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./app"),
    },
  },
  server: {
    port: 14245,
    hmr: {
      port: 14245,
    },
    proxy: {
      // Proxy API requests to the FastAPI backend during development
      '/api': {
        target: 'http://localhost:14250',
        changeOrigin: true,
      },
      '/task': {
        target: 'http://localhost:14250',
        changeOrigin: true,
      },
      // Additional endpoints served by backend (optional)
      '/docs': {
        target: 'http://localhost:14250',
        changeOrigin: true,
      }
    }
  },
})
