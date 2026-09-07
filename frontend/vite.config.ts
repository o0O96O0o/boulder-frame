import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'

function loadFrontendConfig(mode: string) {
  const env = loadEnv(mode, fileURLToPath(new URL('..', import.meta.url)), ['API_BASE_URL', 'MAX_UPLOAD_BYTES'])
  const apiBaseUrl = env.API_BASE_URL || '/'
  const maxUploadBytes = Number(env.MAX_UPLOAD_BYTES || '2147483648')
  if (!Number.isSafeInteger(maxUploadBytes) || maxUploadBytes <= 0) {
    throw new Error('MAX_UPLOAD_BYTES must be a positive safe integer')
  }
  return { api_base_url: apiBaseUrl, max_upload_bytes: maxUploadBytes }
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
