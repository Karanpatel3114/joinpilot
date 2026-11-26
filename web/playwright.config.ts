import { defineConfig, devices } from '@playwright/test'

// End-to-end tests against the real API (inline jobs, no model) and the Vite dev server.
const dataDir = process.env.E2E_DATA_DIR ?? '/tmp/joinpilot-e2e'

export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  retries: process.env.CI ? 1 : 0,
  use: { baseURL: 'http://localhost:5173', trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'uv run uvicorn joinpilot.api.main:app --port 8000',
      cwd: '..',
      url: 'http://localhost:8000/health',
      reuseExistingServer: !process.env.CI,
      env: {
        DATA_DIR: dataDir,
        JOBS_MODE: 'inline',
        LLM__PROVIDER: 'fake',
        KPI__REFERENCE_DATE: '2026-06-30',
        DATABASE_URL: '',
        CORS_ORIGINS: '["http://localhost:5173"]',
      },
      timeout: 60_000,
    },
    {
      command: 'npm run dev -- --port 5173 --strictPort',
      url: 'http://localhost:5173',
      reuseExistingServer: !process.env.CI,
      env: { VITE_API_URL: 'http://localhost:8000' },
      timeout: 60_000,
    },
  ],
})
