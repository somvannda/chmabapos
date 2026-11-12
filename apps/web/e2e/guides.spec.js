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

test("guides: the category page points at the next guide to do", async ({ page }) => {
  await page.goto("/guides/coffee-shop");
  await expect(page.getByText("Start your path")).toBeVisible();
  await expect(page.getByText(/Guide 1 of 12/)).toBeVisible();
  await expect(page.getByRole("button", { name: /Start this guide/i })).toBeVisible();
});

test("guides: the index shows path progress for a returning reader", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("chmaba.guide.progress.v1", JSON.stringify({
      "plan-your-coffee-shop": { step: 3, done: [0, 1, 2, 3], checks: {}, total: 4, complete: true },
    }));
  });
  await page.goto("/guides");
  await expect(page.getByText("1 of 12 complete · Continue")).toBeVisible();
});

test("guides: every step renders a captured product screenshot", async ({ page, request }) => {
  const index = await (await request.get("/api/v1/public/guides")).json();
  expect(index.guides.length).toBeGreaterThan(0);

  for (const guide of index.guides) {
    const detail = await (await request.get(`/api/v1/public/guides/${guide.category_slug}/${guide.slug}`)).json();
    await page.goto(`/guides/${guide.category_slug}/${guide.slug}`);

    for (let step = 0; step < detail.sections.length; step += 1) {
      const image = page.locator("figure img").first();
      await expect(image).toBeVisible();
      const naturalWidth = await image.evaluate((node) => node.naturalWidth);
      expect(naturalWidth, `${guide.slug} step ${step + 1} has no loaded image`).toBeGreaterThan(0);

      if (step < detail.sections.length - 1) {
        await page.getByRole("button", { name: /Next step/i }).click();
        await expect(page.getByRole("heading", { name: detail.sections[step + 1].heading, exact: true })).toBeVisible();
      }
    }
  }
});
