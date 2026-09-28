import { defineConfig, devices } from "@playwright/test";

// End-to-end tests run against the real API + web dev server.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: { baseURL: "http://127.0.0.1:5173", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "python -m uvicorn app.main:app --host 127.0.0.1 --port 8001",
      cwd: "../../chmabapos_api",
      url: "http://127.0.0.1:8001/api/v1/health",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5173 --strictPort",
      url: "http://127.0.0.1:5173",
      env: { VITE_DEV_API_TARGET: "http://127.0.0.1:8001" },
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
