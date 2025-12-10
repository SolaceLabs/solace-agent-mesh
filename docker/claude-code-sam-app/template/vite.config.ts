import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE_PATH || '/',
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: false,  // Allow dynamic port assignment
    hmr: false,  // Disable HMR - requires manual refresh to see changes
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
