// frontend/vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { // Παράδειγμα server options, προσάρμοσέ το
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:5000', // Ο backend server σου
        changeOrigin: true,
      }
    }
  }
})