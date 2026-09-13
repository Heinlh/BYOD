import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  timeout: 840000,
  expect: { timeout: 20000 },
  use: {
    actionTimeout: 30000,
    navigationTimeout: 30000,
    baseURL: 'http://127.0.0.1:18765',
    channel: 'chrome', headless: true,
    viewport: { width: 1360, height: 900 },
    reducedMotion: 'reduce',
    screenshot: 'only-on-failure',
  },
  reporter: 'list',
});
