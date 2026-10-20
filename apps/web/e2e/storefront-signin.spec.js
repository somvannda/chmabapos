import { expect, test } from "@playwright/test";

// Sign-in is a new customer-facing flow, and until now its only verification was
// that it compiles and that the API beneath it is tested. Neither would catch a
// broken route, a broken call to the API, or a form that never advances.
//
// Scope, stated plainly: this covers the entry point - the page rendering and the
// code request actually reaching the API. It does NOT cover the signed-in half,
// because reaching that needs the six-digit code that was emailed, and reading it
// back would couple the suite to mail delivery timing. The signed-in responses are
// covered at the API level instead.

const STOREFRONT = "http://127.0.0.1:3000";

test.describe("Storefront account", () => {
  test("renders the signed-out form and requests a code", async ({ page }) => {
    await page.goto(`${STOREFRONT}/account`);

    await expect(page.getByRole("heading", { name: "Your orders" })).toBeVisible();
    // Passwordless, so there must be no password field anywhere.
    await expect(page.locator('input[type="password"]')).toHaveCount(0);

    const email = page.getByPlaceholder("you@example.com");
    await expect(email).toBeVisible();
    // A fresh visitor is signed out and needs no token to see this much.
    await expect(page.getByRole("button", { name: "Send me a code" })).toBeVisible();

    await email.fill(`signin-e2e-${Date.now()}@example.com`);
    await page.getByRole("button", { name: "Send me a code" }).click();

    // Advancing to the code step is the evidence that the request reached the API
    // and was accepted; the page only moves on after a successful response.
    await expect(page.getByPlaceholder("6-digit code")).toBeVisible();
    await expect(page.locator("form").getByRole("button", { name: "Sign in" })).toBeVisible();

    // ... and nothing crashed on the way.
    await expect(page.getByText("Page could not render")).toHaveCount(0);
  });

  test("a wrong code is refused without saying whether the address exists", async ({ page }) => {
    await page.goto(`${STOREFRONT}/account`);
    await page.getByPlaceholder("you@example.com").fill(`signin-e2e-bad-${Date.now()}@example.com`);
    await page.getByRole("button", { name: "Send me a code" }).click();
    await expect(page.getByPlaceholder("6-digit code")).toBeVisible();

    await page.getByPlaceholder("6-digit code").fill("000000");
    await page.locator("form").getByRole("button", { name: "Sign in" }).click();

    // One message for every failure, matching the API - being more specific would
    // help someone guess codes.
    await expect(page.getByText("That code is not valid.")).toBeVisible();
    // And the page stays usable rather than dead-ending.
    await expect(page.locator("form").getByRole("button", { name: "Sign in" })).toBeVisible();
  });
});
