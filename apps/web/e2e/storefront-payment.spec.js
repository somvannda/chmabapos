import { test, expect } from "@playwright/test";

// The money path that had no coverage: a shopper paying by KHQR.
//
// The existing storefront specs place an order against a store that does *not* require
// payment, so they prove the cart and the confirmation but never the thing a shop
// actually gets paid by. This one turns online payment on and follows the whole way -
// cart, order, QR raised, payment completed, payment recorded as paid.
//
// The provider is the local mock (CHAMABAPAY_MODE defaults to "mock"), because no
// sandbox exists for ChambaPay; its completion endpoint is the same one the POS specs
// use. Worth knowing: the mock's checkout_url points at port 8000 while the test API
// runs on 8001, so the spec never follows that link - it asserts the QR was raised and
// then completes the payment through the API.

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

test.describe("Storefront KHQR payment", () => {
  let token;
  let storeId;
  let storeUrl;
  let productName;

  test.beforeAll(async ({ request }) => {
    const email = `e2e-khqr-${Date.now()}@example.com`;
    const password = "strong-password";
    const registered = await call(request, "post", "/auth/register", {
      data: { email, full_name: "E2E KHQR Owner", password },
    });
    await call(request, "post", "/auth/verify-email", { data: { token: registered.dev_verification_token } });
    token = (await call(request, "post", "/auth/login", { data: { email, password } })).access_token;

    const workspace = await call(request, "post", "/workspaces/setup", {
      token,
      data: {
        company_name: "E2E KHQR Co",
        store_name: "Front Counter",
        country: "Cambodia",
        currency_code: "USD",
        plan_code: "free",
      },
    });
    storeId = workspace.store.id;

    // A plan payment is raised during setup; leaving it pending would be noise.
    if (workspace.billing_payment?.external_id) {
      await call(request, "post", `/mock/chamabapay/${workspace.billing_payment.external_id}/complete`);
    }
    // KHQR needs an active merchant link on the company, the same prerequisite the
    // POS collect/deposit specs set up.
    await call(request, "patch", "/company", {
      token,
      data: { aba_payway_link: "https://link.payway.com.kh/ABAPAYe2ekhqr" },
    });

    const categories = await call(request, "get", "/categories", { token });
    productName = `E2E QR Latte ${Date.now()}`;
    await call(request, "post", "/products", {
      token,
      storeId,
      data: {
        name: productName,
        sku: `E2E-QR-${Date.now()}`,
        price: "4.00",
        opening_stock: 5,
        ...(categories[0] ? { category_id: categories[0].id } : {}),
      },
    });

    await call(request, "patch", `/stores/${storeId}/public-order`, { token, data: { enabled: true } });
    // The whole point: this store insists on being paid before the order lands.
    await call(request, "patch", `/stores/${storeId}`, {
      token,
      data: { preferences: { public_order_require_payment: true } },
    });

    const current = await call(request, "get", "/workspaces/current", { token, storeId });
    storeUrl = `${STOREFRONT}/${current.company.slug}/${current.store.slug}`;
  });

  test("a shopper pays by KHQR, and the payment is recorded as paid", async ({ page, request }) => {
    await page.goto(storeUrl);

    await expect(page.getByRole("heading", { name: "Front Counter" })).toBeVisible();
    await expect(page.getByText(productName)).toBeVisible();

    await page.getByRole("button", { name: `Add one ${productName}` }).click();
    await expect(page.getByText("1 item")).toBeVisible();

    await page.getByRole("button", { name: "View cart" }).click();
    await page.getByPlaceholder("Your name (optional)").fill("Sokha");
    await page.getByRole("button", { name: "Place order" }).click();

    // The order is taken, and because this store requires payment the shopper is asked to
    // pay rather than told to settle at the counter. The heading says so: an unpaid order
    // must never read as placed, or a shopper is told they are finished when they are not.
    await expect(page.getByRole("heading", { name: "Pay to place your order" })).toBeVisible();
    const payLink = page.getByRole("link", { name: /Open the payment page instead/i });
    await expect(payLink).toBeVisible();
    await expect(page.getByText(/pay at the counter/i)).toHaveCount(0);

    // The link carries the provider payment id, which is what completes it.
    const checkoutUrl = await payLink.getAttribute("href");
    const paymentId = (checkoutUrl || "").split("/").filter(Boolean).pop();
    expect(paymentId, `no payment id in ${checkoutUrl}`).toBeTruthy();

    // The shopper pays. In the real world this is the ChambaPay hosted page; here it is
    // the mock's completion endpoint, exactly as the POS specs do it.
    await call(request, "post", `/mock/chamabapay/${paymentId}/complete`);

    // And the shop can see it was paid: the same order, read back through the till.
    const listed = await call(request, "get", "/orders", { token, storeId });
    const orders = Array.isArray(listed) ? listed : listed.items || listed.orders || [];
    const match = orders.find((order) => (order.payments || []).some((payment) => payment.external_id === paymentId));
    expect(match, "the storefront order is not on the till's list").toBeTruthy();

    const detail = await call(request, "get", `/orders/${match.id}`, { token, storeId });
    const payment = (detail.payments || []).find((row) => row.external_id === paymentId);
    expect(payment, "the payment is missing from the order").toBeTruthy();
    expect(payment.status).toBe("paid");

    // And the shopper's own screen notices, with no reload and no second tap: it polls the
    // payment's state. The timeout is generous because the page asks every few seconds, and
    // this is the assertion that fails if the poll loses its answer - the failure that is
    // invisible by hand, because a stale screen looks exactly like a slow payment.
    await expect(page.getByRole("heading", { name: "Order placed" })).toBeVisible({ timeout: 20000 });
  });
});
