import { test, expect } from "@playwright/test";

// The POS half of the chat has no other automated coverage: the storefront spec
// proves a shopper can write, and the API tests prove the endpoints, but nothing
// drives the merchant inbox - the nav wiring, the conversation list, or the
// reply composer. A change to any of those could break the seller's only way to
// answer without a single test failing.
//
// It creates the thread through the public API, then answers it through the UI.

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

test.describe("Seller inbox", () => {
  let token;
  let storeId;
  let username;
  let conversationId;

  test.beforeAll(async ({ request }) => {
    const email = `e2e-inbox-${Date.now()}@example.com`;
    const password = "strong-password";
    const registered = await call(request, "post", "/auth/register", { data: { email, full_name: "E2E Inbox Owner", password } });
    await call(request, "post", "/auth/verify-email", { data: { token: registered.dev_verification_token } });
    const login = await call(request, "post", "/auth/login", { data: { email, password } });
    token = login.access_token;

    const workspace = await call(request, "post", "/workspaces/setup", {
      token,
      data: { company_name: "E2E Inbox Co", store_name: "Inbox Counter", country: "Cambodia", currency_code: "USD", plan_code: "free" },
    });
    storeId = workspace.store.id;
    username = sanitizeUsername(email);

    // The store page must be live for a shopper to open a chat.
    await call(request, "patch", `/stores/${storeId}/public-order`, { token, data: { enabled: true } });
    const current = await call(request, "get", "/workspaces/current", { token, storeId });
    const started = await call(request, "post", `/public/store/${current.company.slug}/${current.store.slug}/chat/messages`, {
      data: { body: "Do you deliver to Riverside?", name: "Dara", phone: "+855 12 345 678" },
    });
    conversationId = started.conversation.id;
  });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(([key, value]) => window.localStorage.setItem(key, value), ["chmaba.access_token", token]);
  });

  test("the seller sees the thread, opens it, and replies", async ({ page, request }) => {
    await page.goto(`/${username}/inbox`);

    // The shopper's message reached the list.
    await expect(page.getByText("Do you deliver to Riverside?").first()).toBeVisible();

    // Open the thread from the list.
    await page.getByRole("button", { name: /Dara/ }).first().click();

    // Reply. The composer is the only way a store answers a customer.
    const answer = `Yes, within 5km ${Date.now()}.`;
    await page.getByPlaceholder("Write a reply").fill(answer);
    await page.getByRole("button", { name: "Send", exact: true }).click();

    // The reply is in the thread the seller is reading.
    await expect(page.getByText(answer).first()).toBeVisible();

    // ...and on the thread the API reports, as a seller message.
    const thread = await call(request, "get", `/store-chat/conversations/${conversationId}`, { token, storeId });
    expect(thread.messages.some((message) => message.body === answer && message.sender_type === "seller")).toBe(true);
  });

  // A phone is the common way a small store answers its shoppers. The composer
  // used to sit below the browser chrome and the customer panel was unreachable,
  // so this drives the screen at a phone width instead of a desktop one.
  test("a phone can reply and open the customer details", async ({ page, request }) => {
    // A long thread is what broke the layout: the thread column grew past the
    // viewport, so the composer was pushed off screen and nothing could scroll.
    for (let index = 0; index < 24; index += 1) {
      await call(request, "post", `/store-chat/conversations/${conversationId}/messages`, {
        token,
        storeId,
        data: { kind: "text", body: `Reply ${index + 1} with enough text to take a couple of lines on a phone.` },
      });
    }

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`/${username}/inbox`);
    await page.getByRole("button", { name: /Dara/ }).first().click();

    // The reply box and send button are on screen, not below the fold.
    const composer = page.getByPlaceholder("Write a reply");
    await expect(composer).toBeVisible();
    const box = await composer.boundingBox();
    expect(box.y + box.height).toBeLessThanOrEqual(844);

    const answer = `On my phone ${Date.now()}.`;
    await composer.fill(answer);
    await page.getByRole("button", { name: "Send", exact: true }).click();
    // Scope to the thread: the same text also sits in the hidden conversation
    // list at phone width, and only the bubble proves the reply landed.
    await expect(page.locator("section").getByText(answer)).toBeVisible();

    // The messages scroll inside the thread instead of stretching the page.
    const list = await page.locator(".overscroll-contain").evaluate((element) => {
      const metrics = { scrollHeight: element.scrollHeight, clientHeight: element.clientHeight };
      element.scrollTop = 0;
      return { ...metrics, scrollTop: element.scrollTop };
    });
    expect(list.scrollHeight).toBeGreaterThan(list.clientHeight);
    expect(list.scrollTop).toBe(0);

    // The customer's details are reachable from the thread header.
    await page.getByRole("button", { name: "Customer details" }).click();
    const details = page.getByRole("dialog", { name: "Customer details" });
    await expect(details).toBeVisible();
    await expect(details.getByText("+855 12 345 678")).toBeVisible();
    await page.getByRole("button", { name: "Close thread details" }).click();
    await expect(details).toHaveCount(0);
  });
});
