import { test, expect } from "@playwright/test";

// Table QR dine-in, driven through the real storefront dev server. The point of
// this suite is the thing that used to be broken: a table code must survive the
// hand-off from the legacy `/order/<token>` link to the branded store page, and
// the resulting ticket must be a dine-in ticket on that table - never a takeaway.

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

test.describe("Storefront dine-in (table QR)", () => {
  let token;
  let storeId;
  let table;
  let productName;
  let storeUrl;
  let tableUrl;

  test.beforeAll(async ({ request }) => {
    const email = `e2e-dinein-${Date.now()}@example.com`;
    const password = "strong-password";
    const registered = await call(request, "post", "/auth/register", {
      data: { email, full_name: "E2E Dine-in Owner", password },
    });
    await call(request, "post", "/auth/verify-email", { data: { token: registered.dev_verification_token } });
    const login = await call(request, "post", "/auth/login", { data: { email, password } });
    token = login.access_token;

    const workspace = await call(request, "post", "/workspaces/setup", {
      token,
      data: {
        company_name: "E2E Dine In Co",
        store_name: "Dine In Counter",
        country: "Cambodia",
        currency_code: "USD",
        plan_code: "pro",
      },
    });
    storeId = workspace.store.id;
    // Table management is a paid feature; a plan is only in force once its first
    // billing payment completes, exactly as a real checkout does.
    if (workspace.billing_payment?.external_id) {
      await call(request, "post", `/mock/chamabapay/${workspace.billing_payment.external_id}/complete`);
    }

    const categories = await call(request, "get", "/categories", { token, storeId });
    productName = `E2E DineIn Dish ${Date.now()}`;
    await call(request, "post", "/products", {
      token,
      storeId,
      data: {
        name: productName,
        sku: `E2E-DI-${Date.now()}`,
        price: "5.00",
        category_id: categories[0].id,
        opening_stock: 20,
      },
    });

    table = await call(request, "post", "/dining/tables", { token, storeId, data: { name: "T1", seats: 2 } });
    await call(request, "patch", `/stores/${storeId}/public-order`, { token, data: { enabled: true } });

    const current = await call(request, "get", "/workspaces/current", { token, storeId });
    storeUrl = `${STOREFRONT}/${current.company.slug}/${current.store.slug}`;
    tableUrl = `${storeUrl}/t/${table.qr_token}`;
  });

  test("a table QR opens dine-in mode and the order is attributed to the table", async ({ page, request }) => {
    await page.goto(tableUrl);

    // The page knows both identities, not just the store.
    await expect(page.getByRole("heading", { name: "Dine In Counter" })).toBeVisible();
    await expect(page.getByText(/Table T1/)).toBeVisible();

    await page.getByRole("button", { name: `Add one ${productName}` }).click();
    await page.getByRole("button", { name: "View cart" }).click();
    await page.getByRole("button", { name: "Place order" }).click();

    await expect(page.getByRole("heading", { name: "Order placed" })).toBeVisible();
    await expect(page.getByText(/with the kitchen/)).toBeVisible();

    // The board must see a dine-in ticket on that table, not an online takeaway.
    const tickets = await call(request, "get", "/held-orders", { token, storeId });
    const ticket = tickets.find((row) => row.table_id === table.id);
    expect(ticket, "a ticket tied to the table should exist").toBeTruthy();
    expect(ticket.source).toBe("qr");
    expect(ticket.order_type).toBe("dine_in");
  });

  test("?table= is redirected to the canonical /t/ path", async ({ page }) => {
    await page.goto(`${storeUrl}?table=${table.qr_token}`);

    await expect(page).toHaveURL(new RegExp(`/t/${table.qr_token}$`));
    await expect(page.getByText(/Table T1/)).toBeVisible();
  });

  test("an unknown table code is refused, not downgraded to a takeaway", async ({ page }) => {
    await page.goto(`${storeUrl}/t/not-a-real-table`);

    await expect(page.getByText(/table link is no longer active/i)).toBeVisible();
  });

  test("the table page is not indexable", async ({ page }) => {
    await page.goto(tableUrl);

    await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", "noindex");
  });
});
