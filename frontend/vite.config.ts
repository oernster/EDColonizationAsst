import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  // The built app is served by FastAPI under /app, so we set the base
  // path accordingly. In development, the Vite dev server will also
  // serve the app at http://localhost:5173/app/.
  base: '/app/',
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
  build: {
    /**
     * The main bundle is currently ~502 kB after minification, which trips
     * Vite's default 500 kB warning. This is acceptable for this app, so we
     * raise the warning threshold slightly to avoid noise in CI logs.
     */
    chunkSizeWarningLimit: 800,
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})
