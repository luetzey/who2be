/// <reference types="vitest/config" />
import path from 'node:path'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Build-Zeit-Edition-Flag (ADR-0029): steuert, ob die Billing-UI ins Bundle
// kommt. `__CLOUD_BUILD__` wird als Literal ersetzt → der On-Prem-Build (Default)
// tree-shaked `features/billing` komplett aus dem ausgelieferten JS.
const isCloudBuild = (process.env.VITE_WHO2BE_EDITION ?? 'onprem') === 'cloud'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: {
    __CLOUD_BUILD__: JSON.stringify(isCloudBuild),
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
