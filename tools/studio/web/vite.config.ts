import vue from '@vitejs/plugin-vue'
import { configDefaults, defineConfig } from 'vitest/config'

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
  // e2e/ holds Playwright specs, which vitest would otherwise pick up by their .spec.ts names.
  test: { environment: 'happy-dom', globals: true, exclude: [...configDefaults.exclude, 'e2e/**'] },
})
