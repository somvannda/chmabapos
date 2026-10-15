import { test, expect } from "@playwright/test";

// The order-tracking token has API coverage, but nothing had ever followed the
// link a customer is actually given. This drives the real thing: place an order
// on the storefront, click "Follow this order", and read the status page.
//
// It also checks the failure path, because a status page that shows a customer
// *someone else's* order would be a far worse bug than one that 404s.

const API = "http://127.0.0.1:8001/api/v1";
const STOREFRONT = "http://127.0.0.1:3000";

async function call(request, method, path, { token, storeId, data } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (storeId) headers["X-Store-ID"] = storeId;
  const response = await request[method](`${API}${path}`, { headers, data });
  if (!response.ok()) throw new Error(`${method.toUpperCase()} ${path} -> ${response.status()} ${await response.text()}`);
  return response.status() === 204 ? null : response.json();
}

test.describe("Storefront order tracking", () => {
  let storeUrl;
  let productName;

  test.beforeAll(async ({ request }) => {
    const stamp = Date.now();
    const email = `e2e-tracking-${stamp}@example.com`;
    const password = "strong-password";
    const registered = await call(request, "post", "/auth/register", {
      data: { email, full_name: "E2E Tracking Owner", password },
    });
    await call(request, "post", "/auth/verify-email", { data: { token: registered.dev_verification_token } });
    const login = await call(request, "post", "/auth/login", { data: { email, password } });
    const token = login.access_token;

    const workspace = await call(request, "post", "/workspaces/setup", {
      token,
      data: {
        company_name: "E2E Tracking Co",
        store_name: "Tracking Counter",
        country: "Cambodia",
        currency_code: "USD",
        plan_code: "free",
      },
    });
    const storeId = workspace.store.id;

    const categories = await call(request, "get", "/categories", { token });
    productName = `E2E Tracked Latte ${stamp}`;
    await call(request, "post", "/products", {
      token,
      storeId,
      data: {
        name: productName,
        sku: `E2E-TR-${stamp}`,
        price: "4.00",
        category_id: categories[0].id,
        opening_stock: 5,
      },
    });
    await call(request, "patch", `/stores/${storeId}/public-order`, { token, data: { enabled: true } });

    const current = await call(request, "get", "/workspaces/current", { token, storeId });
    storeUrl = `${STOREFRONT}/${current.company.slug}/${current.store.slug}`;
  });

  test("a customer can follow the order they just placed", async ({ page }) => {
    await page.goto(storeUrl);
    await page.getByRole("button", { name: `Add one ${productName}` }).click();
    await page.getByRole("button", { name: "View cart" }).click();
    await page.getByPlaceholder("Your name (optional)").fill("Sokha");
    await page.getByRole("button", { name: "Place order" }).click();

    await expect(page.getByRole("heading", { name: "Order placed" })).toBeVisible();

    // The link the customer is actually given.
    await page.getByRole("link", { name: "Follow this order" }).click();

    // The status page, rendered from the token.
    await expect(page.getByRole("heading", { name: "Order received" })).toBeVisible();
    await expect(page.getByText("Tracking Counter")).toBeVisible();
    await expect(page.getByText(/^\$\d+\.\d{2}$/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Refresh status" })).toBeVisible();
  });

  test("an unknown token shows a friendly not-found rather than an error", async ({ page }) => {
    await page.goto(`${STOREFRONT}/order/definitely-not-a-real-token`);

    await expect(page.getByRole("heading", { name: /can't find that order/i })).toBeVisible();
    // And it must not leak anything resembling a customer's order.
    await expect(page.getByText("Refresh status")).toHaveCount(0);
    await expect(page.getByText("Page could not render")).toHaveCount(0);
  });
});
