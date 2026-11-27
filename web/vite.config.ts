/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// A Vercel build without the API address would call localhost from the live site.
if (process.env.VERCEL && !process.env.VITE_API_URL) {
  throw new Error('Set VITE_API_URL in the Vercel project settings (see infra/DEPLOY.md).')
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
  },
})
