import { readFileSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

function loadFrontendConfig(mode: string) {
  const filename = mode === 'development' ? 'config.dev.json' : 'config.json'
  const path = fileURLToPath(new URL(`./conf/${filename}`, import.meta.url))
  const source = readFileSync(path, 'utf8').replace(/\$\{([A-Za-z_][A-Za-z0-9_]*)\}/g, (_, key: string) => process.env[key] ?? '')
  const config = JSON.parse(source) as { api_base_url?: string; max_upload_bytes?: number }
  if (!config.api_base_url || !config.max_upload_bytes) throw new Error(`frontend configuration is incomplete: ${path}`)
  return config
}

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  define: {
    __BOULDER_FRAME_CONFIG__: JSON.stringify(loadFrontendConfig(mode)),
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'node',
    globals: true,
  },
}))
