/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // Vitest: los tests de lógica corren en node (rápido); los de componente
  // (.test.tsx) necesitan DOM → jsdom solo para ellos.
  test: {
    environmentMatchGlobs: [['**/*.test.tsx', 'jsdom']],
    // Node 22+ define su propio `localStorage` global (undefined sin
    // --localstorage-file) y pisa al de jsdom. Ver src/test/setupStorage.ts.
    setupFiles: ['./src/test/setupStorage.ts'],
  },
  build: {
    chunkSizeWarningLimit: 1400,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react':    ['react', 'react-dom', 'react-router-dom'],
          'vendor-motion':   ['motion'],
          'vendor-lucide':   ['lucide-react'],
          'vendor-zustand':  ['zustand'],
          'vendor-mediapipe':['@mediapipe/tasks-vision'],
        },
      },
    },
  },
  server: {
    port: 5173,
    host: true,
    allowedHosts: ['.ngrok-free.app', '.ngrok.io', '.ngrok.app', '.trycloudflare.com', '.loca.lt'],
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  }
})
