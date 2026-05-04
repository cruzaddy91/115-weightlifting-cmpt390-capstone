import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        // 127.0.0.1 explicitly so Node does not resolve localhost to ::1 and
        // hit ECONNREFUSED when Django only binds IPv4 (Django's default).
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      }
    }
  }
})

