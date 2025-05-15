// frontend/vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173, // Το port που χρησιμοποιείς
    proxy: {
      // Proxy API requests to Flask backend
      '/api': { // Αν τα API σου είναι κάτω από /api
        target: 'http://localhost:5000', // Το backend σου
        changeOrigin: true,
        // secure: false, // Αν το backend τρέχει σε http
        // rewrite: (path) => path.replace(/^\/api/, '') // Αν δεν θέλεις το /api να πηγαίνει στο backend
      }
    }
  }
})