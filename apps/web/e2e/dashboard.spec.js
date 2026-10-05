import { test, expect } from "@playwright/test";

const API = "http://127.0.0.1:8001/api/v1";

function sanitizeUsername(email) {
  return (email.split("@")[0] || "user").toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "user";
}

async function call(request, method, path, { token, storeId, data } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (storeId) headers["X-Store-ID"] = storeId;
  const response = await request[method](`${API}${path}`, { headers, data });
  if (!response.ok()) throw new Error(`${method.toUpperCase()} ${path} -> ${response.status()} ${await response.text()}`);
  return response.status() === 204 ? null : response.json();
}

test.describe("Overview dashboard", () => {
  let token;
  let storeId;
  let username;

  test.beforeAll(async ({ request }) => {
    const email = `e2e-dash-${Date.now()}@example.com`;
    const password = "strong-password";
    const registered = await call(request, "post", "/auth/register", { data: { email, full_name: "E2E Owner", password } });
    await call(request, "post", "/auth/verify-email", { data: { token: registered.dev_verification_token } });
    const login = await call(request, "post", "/auth/login", { data: { email, password } });
    token = login.access_token;
    const workspace = await call(request, "post", "/workspaces/setup", {
      token,
      data: { company_name: "E2E Store", store_name: "Main Counter", country: "Cambodia", currency_code: "USD", plan_code: "free" },
    });
    storeId = workspace.store.id;
    username = sanitizeUsername(email);
    // One product so the inventory-derived panels have data to shape.
    await call(request, "post", "/products", { token, storeId, data: { name: "E2E Overview Item", sku: `E2E-OV-${Date.now()}`, price: "12.50" } });
  });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(([key, value]) => window.localStorage.setItem(key, value), ["chmaba.access_token", token]);
  });

  test("renders the real overview sections without crashing", async ({ page }) => {
    await page.goto(`/${username}/dashboard`);

    await expect(page.getByRole("heading", { name: /Good (morning|afternoon|evening), E2E Store/ })).toBeVisible();
    await expect(page.getByText(/Live workspace/).first()).toBeVisible();

    // Period selector defaults to Today.
    await expect(page.getByRole("button", { name: "Today" })).toBeVisible();

    // KPI cards backed by the report summary.
    for (const label of ["Net sales", "Transactions", "Average order", "Items sold"]) {
      await expect(page.getByText(label, { exact: true })).toBeVisible();
    }

    // Data panels.
    await expect(page.getByRole("heading", { name: "Sales trend" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Needs attention" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Recent transactions" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Top products" })).toBeVisible();

    // A fresh workspace has no paid orders yet.
    await expect(page.getByText(/No paid orders today yet\./)).toBeVisible();

    // The setup checklist moved out of the Overview; it lives in the floating coach.
    await expect(page.getByText("Finish setting up")).toHaveCount(0);
    await expect(page.getByText("Page could not render")).toHaveCount(0);
  });

  test("switching the period keeps the overview rendering", async ({ page }) => {
    await page.goto(`/${username}/dashboard`);

    await page.getByRole("button", { name: "Today" }).click();
    await page.getByRole("option", { name: "Last 7 days" }).click();

    await expect(page.getByRole("button", { name: "Last 7 days" })).toBeVisible();
    await expect(page.getByText(/happening at your store/)).toContainText("last 7 days");
    await expect(page.getByText("Page could not render")).toHaveCount(0);
  });
});
