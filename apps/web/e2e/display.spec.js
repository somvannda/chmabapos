import { test, expect } from "@playwright/test";

const SNAPSHOT_KEY = "chmaba.customer-display.snapshot";

// The display window renders whatever the POS last published. Seeding the
// shared localStorage snapshot exercises the same shape without needing a live
// cashier session.
function snapshot(overrides = {}) {
  return {
    storeName: "Main Counter",
    currency: "USD",
    items: [{ key: "p1", name: "E2E Coffee", quantity: 2, unitPrice: 3.5, lineTotal: 7 }],
    itemCount: 2,
    subtotal: 7,
    discount: 0,
    tax: 0.7,
    taxLabel: "Service tax",
    tip: 0,
    total: 7.7,
    status: "cart",
    payment: null,
    orderNumber: null,
    updatedAt: Date.now(),
    ...overrides,
  };
}

async function seed(page, value) {
  await page.addInitScript(([key, raw]) => window.localStorage.setItem(key, raw), [SNAPSHOT_KEY, JSON.stringify(value)]);
}

test.describe("Customer display", () => {
  test("renders the running order from the shared snapshot", async ({ page }) => {
    await seed(page, snapshot());
    await page.goto("/display");
    await expect(page).toHaveURL(/\/display$/);
    await expect(page.getByRole("heading", { name: "Your order" })).toBeVisible();
    await expect(page.getByText("E2E Coffee")).toBeVisible();
    await expect(page.getByText("$7.70")).toBeVisible();
  });

  test("shows the KHQR code and amount while payment is pending", async ({ page }) => {
    await seed(page, snapshot({ status: "payment", payment: { qrString: "000201010212", amount: 7.7, currency: "USD", externalId: "ext-1" } }));
    await page.goto("/display");
    await expect(page.getByText("KHQR")).toBeVisible();
    await expect(page.getByText("Scan with any Bakong-enabled banking app")).toBeVisible();
    await expect(page.getByText("$7.70").first()).toBeVisible();
  });

  test("shows a thank-you state after payment", async ({ page }) => {
    await seed(page, snapshot({ status: "paid" }));
    await page.goto("/display");
    await expect(page.getByText("Thank you!")).toBeVisible();
    await expect(page.getByText("Payment received")).toBeVisible();
  });
});
