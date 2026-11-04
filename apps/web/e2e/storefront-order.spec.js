import { test, expect } from "@playwright/test";

// The storefront is a separate origin from the portal, so this suite drives the
// real storefront dev server (started from playwright.config.js) rather than
// mounting a component. That is also the only way to cover the thing that
// actually earns money: a shopper building a cart and placing an order.

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

test.describe("Storefront order flow", () => {
  let storeUrl;
  let productName;

  test.beforeAll(async ({ request }) => {
    const email = `e2e-storefront-${Date.now()}@example.com`;
    const password = "strong-password";
    const registered = await call(request, "post", "/auth/register", {
      data: { email, full_name: "E2E Storefront Owner", password },
    });
    await call(request, "post", "/auth/verify-email", { data: { token: registered.dev_verification_token } });
    const login = await call(request, "post", "/auth/login", { data: { email, password } });
    const token = login.access_token;

    const workspace = await call(request, "post", "/workspaces/setup", {
      token,
      data: {
        company_name: "E2E Storefront Co",
        store_name: "Front Counter",
        country: "Cambodia",
        currency_code: "USD",
        plan_code: "starter",
      },
    });
    const storeId = workspace.store.id;
    // Serials, the seller inbox and the storefront are Starter features now, and
    // a plan is only in force once its first billing payment completes.
    if (workspace.billing_payment?.external_id) {
      await call(request, "post", `/mock/chamabapay/${workspace.billing_payment.external_id}/complete`);
    }


    const categories = await call(request, "get", "/categories", { token });
    productName = `E2E Front Latte ${Date.now()}`;
    await call(request, "post", "/products", {
      token,
      storeId,
      data: {
        name: productName,
        sku: `E2E-SF-${Date.now()}`,
        price: "4.00",
        category_id: categories[0].id,
        opening_stock: 5,
      },
    });

    // The store page is only served once the store opts into online ordering.
    await call(request, "patch", `/stores/${storeId}/public-order`, { token, data: { enabled: true } });

    // Read the slugs back rather than predicting how the API slugifies names.
    const current = await call(request, "get", "/workspaces/current", { token, storeId });
    storeUrl = `${STOREFRONT}/${current.company.slug}/${current.store.slug}`;
  });

  test("a shopper can build a cart and place an order", async ({ page }) => {
    await page.goto(storeUrl);

    // The page is server-rendered, so the store name is present before hydration.
    await expect(page.getByRole("heading", { name: "Front Counter" })).toBeVisible();
    await expect(page.getByText(productName)).toBeVisible();
    await expect(page.getByText("$4.00").first()).toBeVisible();

    await page.getByRole("button", { name: `Add one ${productName}` }).click();
    await page.getByRole("button", { name: `Add one ${productName}` }).click();

    // The cart bar shows the running total (2 x 4.00).
    await expect(page.getByText("2 items")).toBeVisible();
    await expect(page.getByText("$8.00")).toBeVisible();

    await page.getByRole("button", { name: "View cart" }).click();
    await page.getByPlaceholder("Your name (optional)").fill("Sokha");
    await page.getByRole("button", { name: "Place order" }).click();

    // Confirmation, and the ticket is real: it lands on the kitchen board.
    await expect(page.getByRole("heading", { name: "Order placed" })).toBeVisible();
    await expect(page.getByText(/Front Counter has your order/)).toBeVisible();
  });

  test("asking for more than the shelf holds surfaces the API's own message", async ({ page }) => {
    await page.goto(storeUrl);

    // Stock is 5; the counter is hidden from the client, so the server is what
    // decides. Proving the rejection reaches the shopper is the point.
    const add = page.getByRole("button", { name: `Add one ${productName}` });
    for (let index = 0; index < 6; index += 1) await add.click();

    await page.getByRole("button", { name: "View cart" }).click();
    await page.getByRole("button", { name: "Place order" }).click();

    await expect(page.getByText(/Insufficient stock/)).toBeVisible();
    // And the cart is kept, so the shopper can correct it rather than starting over.
    await expect(page.getByRole("button", { name: "Place order" })).toBeVisible();
  });
});
