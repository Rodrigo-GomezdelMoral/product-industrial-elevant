import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: 'tests',
  timeout: 120_000,
  use: { baseURL: 'http://127.0.0.1:4173', acceptDownloads: true },
  webServer: [
    {
      command: 'python -m uvicorn app.main:app --port 8000',
      cwd: '..',
      url: 'http://127.0.0.1:8000/healthz',
      env: { ELEVANT_DOUBLES: 'true' },
      reuseExistingServer: true,
    },
    { command: 'npm run preview', url: 'http://127.0.0.1:4173', reuseExistingServer: true },
  ],
})
