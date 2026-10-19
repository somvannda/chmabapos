import { test, expect } from "@playwright/test";

// Choosing an add-on on the storefront, end to end: the product page offers the
// shop's own groups, a required group blocks the add until it is answered, and the
// chosen add-on reaches the ticket priced from the catalogue.

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

test.describe("Storefront add-ons", () => {
  let token;
  let storeId;
  let product;
  let productName;
  let productUrl;

  test.beforeAll(async ({ request }) => {
    const email = `e2e-modifiers-${Date.now()}@example.com`;
    const password = "strong-password";
    const registered = await call(request, "post", "/auth/register", { data: { email, full_name: "E2E Add-on Owner", password } });
    await call(request, "post", "/auth/verify-email", { data: { token: registered.dev_verification_token } });
    token = (await call(request, "post", "/auth/login", { data: { email, password } })).access_token;

    const workspace = await call(request, "post", "/workspaces/setup", {
      token,
      data: { company_name: "E2E Add-on Co", store_name: "Add-on Counter", country: "Cambodia", currency_code: "USD", plan_code: "pro" },
    });
    storeId = workspace.store.id;
    if (workspace.billing_payment?.external_id) {
      await call(request, "post", `/mock/chamabapay/${workspace.billing_payment.external_id}/complete`);
    }

    const group = await call(request, "post", "/modifier-groups", {
      token,
      data: {
        name: "Milk",
        min_select: 1,
        max_select: 1,
        is_required: true,
        modifiers: [
          { name: "Oat", price_delta: "0.50" },
          { name: "Whole", price_delta: "0.00" },
        ],
      },
    });
    const categories = await call(request, "get", "/categories", { token, storeId });
    productName = `E2E Flat White ${Date.now()}`;
    product = await call(request, "post", "/products", {
      token,
      storeId,
      data: { name: productName, sku: `E2E-MOD-${Date.now()}`, price: "3.00", category_id: categories[0].id, opening_stock: 10, modifier_group_id: group.id },
    });
    await call(request, "patch", `/stores/${storeId}/public-order`, { token, data: { enabled: true } });

    const current = await call(request, "get", "/workspaces/current", { token, storeId });
    productUrl = `${STOREFRONT}/${current.company.slug}/${current.store.slug}/product/${product.id}`;
  });

  test("a required add-on blocks the add until chosen, then reaches the ticket", async ({ page, request }) => {
    await page.goto(productUrl);

    // The shop's group is offered, and a required choice must be made first.
    await expect(page.getByText("Milk")).toBeVisible();
    const add = page.getByRole("button", { name: `Add one ${productName}` });
    await expect(add).toBeDisabled();
    await expect(page.getByText("Choose the required options above.")).toBeVisible();

    await page.getByRole("button", { name: /Oat/ }).click();

    // The price shown already includes the add-on, and the line can be added.
    await expect(page.getByText("$3.50").first()).toBeVisible();
    await expect(add).toBeEnabled();
    await add.click();

    // The cart, on the store page, names the add-on beside the product.
    await page.getByRole("link", { name: "View the cart" }).click();
    await page.getByRole("button", { name: "View cart" }).click();
    await expect(page.getByText(/Oat/)).toBeVisible();
    await page.getByRole("button", { name: "Place order" }).click();
    await expect(page.getByRole("heading", { name: "Order placed" })).toBeVisible();

    // The ticket carries the add-on, priced from the catalogue.
    const tickets = await call(request, "get", "/held-orders", { token, storeId });
    const ticket = tickets.find((row) => (row.items || []).some((line) => String(line.product_name) === productName));
    expect(ticket, "a ticket with the add-on line should exist").toBeTruthy();
    const line = ticket.items.find((row) => String(row.product_name) === productName);
    expect(line.modifiers[0].name).toBe("Oat");
    expect(line.modifiers[0].price_delta).toBe("0.50");
    expect(line.unit_price).toBe("3.50");
    expect(ticket.subtotal).toBe("3.50");
  });

  test("a card for a product with add-ons links to the product page instead of adding", async ({ page }) => {
    await page.goto(productUrl.replace(/\/product\/.*$/, ""));

    // Quiet adding would send the line without its required choice, so the card
    // links to the page where the choice is made.
    await expect(page.getByRole("link", { name: "Choose" })).toBeVisible();
    await expect(page.getByRole("button", { name: `Add one ${productName}` })).toHaveCount(0);
  });
});
