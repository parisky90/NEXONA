// frontend/vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173, // Το port που χρησιμοποιείς για το frontend development server
    proxy: {
      // Όλα τα requests που ξεκινούν με /api/v1 (π.χ., /api/v1/login, /api/v1/session)
      // θα προωθούνται στο backend server που τρέχει στο http://localhost:5001.
      // Το Vite dev server θα χειριστεί την αλλαγή του origin.
      '/api/v1': { // Ο PROXY ΑΚΟΥΕΙ ΣΤΟ /api/v1
        target: 'http://localhost:5001', // Το backend σου που τρέχει στο port 5001
        changeOrigin: true, // Σημαντικό για να αλλάζει το Host header στο backend
        // secure: false, // Αν το backend σου τρέχει σε HTTP (όχι HTTPS)
      }
    }
  }
})