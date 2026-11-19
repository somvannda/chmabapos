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
      // The public and auth surfaces are rate-limited per IP in production.
      // This suite drives many real orders and sign-ups from a single address,
      // so the limits are disabled here exactly as the API's own tests do
      // (chmabapos_api/tests/conftest.py). The limits have dedicated coverage in
      // the API suite; here they would only make one spec flake another.
      env: {
        PUBLIC_ORDER_RATE_LIMIT_PER_MINUTE: "0",
        PUBLIC_READ_RATE_LIMIT_PER_MINUTE: "0",
        AUTH_LOGIN_RATE_LIMIT_PER_MINUTE: "0",
        AUTH_LOGIN_FAILURE_LIMIT: "0",
        AUTH_REGISTER_RATE_LIMIT_PER_HOUR: "0",
        AUTH_VERIFY_RATE_LIMIT_PER_MINUTE: "0",
        AUTH_RESEND_RATE_LIMIT_PER_HOUR: "0",
        AUTH_RESET_REQUEST_RATE_LIMIT_PER_HOUR: "0",
        AUTH_RESET_CONFIRM_RATE_LIMIT_PER_HOUR: "0",
      },
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5173 --strictPort",
      url: "http://127.0.0.1:5173",
      // VITE_STOREFRONT_URL mirrors the shipped (go-live) configuration: with it
      // set, the legacy `/order/<token>` link redirects instead of rendering its
      // own menu. Leaving it blank here - the default elsewhere - is what let a
      // table-QR regression ship, so it is set deliberately.
      env: { VITE_DEV_API_TARGET: "http://127.0.0.1:8001", VITE_STOREFRONT_URL: "http://127.0.0.1:3000" },
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      // The storefront mirrors production: the browser reaches the API through
      // this server's own /api proxy (VITE_DEV_API_TARGET), exactly as nginx does
      // on the storefront host, while server-side rendering calls the API
      // directly through INTERNAL_API_URL. No CORS is involved either way.
      command: "npm run dev -- --host 127.0.0.1 --port 3000 --strictPort",
      cwd: "../storefront",
      // The directory, not "/": the root is a redirect, and a readiness probe
      // should not depend on how a redirect is treated.
      url: "http://127.0.0.1:3000/stores",
      env: {
        VITE_DEV_API_TARGET: "http://127.0.0.1:8001",
        INTERNAL_API_URL: "http://127.0.0.1:8001/api/v1",
      },
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
