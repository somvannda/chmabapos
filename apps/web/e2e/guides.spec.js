import { test, expect } from "@playwright/test";

// The public guide reader is the one place a merchant can see the whole setup
// path before signing up, so its two load-bearing behaviours are covered here:
// the cross-guide timeline and resumable step progress.
test("guides: the path timeline shows the position and steps resume after reload", async ({ page }) => {
  await page.goto("/guides");
  await expect(page.getByRole("heading", { name: /Set up your shop/ })).toBeVisible();

  await page.goto("/guides/coffee-shop/ring-up-your-first-sale");

  await expect(page.getByText("Guide 7 of 12").first()).toBeVisible();
  await expect(page.getByText("You are here")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Open the register" })).toBeVisible();
  await expect(page.locator("figure img").first()).toBeVisible();
  await expect(page.getByRole("img", { name: /Open shift records the counted float/ })).toBeVisible();

  await page.getByRole("button", { name: /Next step/i }).click();
  await expect(page.getByRole("heading", { name: "Add the drinks" })).toBeVisible();
  await expect(page).toHaveURL(/#step-2$/);

  // Progress is written to localStorage and the hash, so a reload returns the
  // reader to the step they were on rather than starting over.
  await page.reload();
  await expect(page.getByRole("heading", { name: "Add the drinks" })).toBeVisible();
  await expect(page).toHaveURL(/#step-2$/);
});
