import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

const API_PORT = 8930

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': `http://127.0.0.1:${API_PORT}`,
      '/file': `http://127.0.0.1:${API_PORT}`,
      '/fx-file': `http://127.0.0.1:${API_PORT}`,
    },
  },
  test: { environment: 'happy-dom', globals: true },
})
