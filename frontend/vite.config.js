import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Forward API calls to the FastAPI dev server (uvicorn on :8000).
    proxy: {
      '/api': process.env.CODEU_API_URL ?? 'http://127.0.0.1:8000',
    },
  },
  build: {
    chunkSizeWarningLimit: 700,
  },
})
