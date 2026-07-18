import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// base './' so the built bundle works from a file:// URL inside QtWebEngine
export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss()],
})
