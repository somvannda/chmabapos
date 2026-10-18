import { test, expect } from "@playwright/test";

// The chat is the one customer-facing surface whose whole value is the round
// trip, and nothing else covers it: the API tests prove the endpoints, and the
// unit tests prove the pure helpers, but neither would catch a widget that never
// opens, a send that never reaches the API, or a stream that never delivers a
// reply. So this drives the real storefront against the real API.
//
// The seller half is exercised through the API rather than through the POS UI:
// two browser contexts against one server is a lot of setup for the same
// assertion, and the inbox UI's own rendering is not what would break here.

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

test.describe("Storefront chat", () => {
  let storeUrl;
  let token;
  let storeId;

  test.beforeAll(async ({ request }) => {
    const email = `e2e-chat-${Date.now()}@example.com`;
    const password = "strong-password";
    const registered = await call(request, "post", "/auth/register", {
      data: { email, full_name: "E2E Chat Owner", password },
    });
    await call(request, "post", "/auth/verify-email", { data: { token: registered.dev_verification_token } });
    const login = await call(request, "post", "/auth/login", { data: { email, password } });
    token = login.access_token;

    const workspace = await call(request, "post", "/workspaces/setup", {
      token,
      data: {
        company_name: "E2E Chat Co",
        store_name: "Chat Counter",
        country: "Cambodia",
        currency_code: "USD",
        plan_code: "free",
      },
    });
    storeId = workspace.store.id;

    // The store page is only served once the store opts into online ordering.
    await call(request, "patch", `/stores/${storeId}/public-order`, { token, data: { enabled: true } });
    const current = await call(request, "get", "/workspaces/current", { token, storeId });
    storeUrl = `${STOREFRONT}/${current.company.slug}/${current.store.slug}`;
  });

  test("a guest can message the store and see the reply arrive without reloading", async ({ page, request }) => {
    const question = `Do you deliver to Riverside ${Date.now()}?`;
    const answer = `Yes, within 5km ${Date.now()}.`;
    const guestName = `Sokha ${Date.now()}`;

    await page.goto(storeUrl);

    // The launcher is the entry point; if it is missing, none of the rest matters.
    await page.getByTestId("store-chat-launcher").click();
    await expect(page.getByText("Usually replies within a few minutes")).toBeVisible();

    // The name is optional but, when given, is what the store sees instead of "Guest".
    await page.getByLabel("Your name").fill(guestName);
    await page.getByPlaceholder("Write a message").fill(question);
    await page.getByRole("button", { name: "Send" }).click();

    // The guest's own message is echoed into the thread, which only happens after
    // the API accepted it.
    await expect(page.getByText(question)).toBeVisible();

    // The store's inbox has the thread, and it reads as unread.
    const conversations = await call(request, "get", "/store-chat/conversations", { token, storeId });
    expect(conversations.length).toBeGreaterThan(0);
    const conversation = conversations[0];
    expect(conversation.last_message_preview).toContain("Riverside");
    expect(conversation.unread_count).toBe(1);
    // The typed name reached the thread, so the seller is not looking at "Guest".
    expect(conversation.guest_name).toBe(guestName);

    // Opening the thread is what clears the store's badge.
    const thread = await call(request, "get", `/store-chat/conversations/${conversation.id}`, { token, storeId });
    expect(thread.messages.length).toBe(1);
    expect((await call(request, "get", "/store-chat/unread-count", { token, storeId })).unread).toBe(0);

    // The seller replies. Give `request` a moment before asserting on the browser.
    const reply = await call(request, "post", `/store-chat/conversations/${conversation.id}/messages`, {
      token,
      storeId,
      data: { kind: "text", body: answer },
    });
    expect(reply.message.sender_type).toBe("seller");

    // The reply reaches the open page over the stream - no reload, no click. This
    // is the assertion the whole spec exists for.
    await expect(page.getByText(answer)).toBeVisible({ timeout: 20000 });

    // The customer sees the store, not the person who typed: the seller's account
    // name must never appear in the shopper's widget.
    await expect(page.getByText("E2E Chat Owner")).toHaveCount(0);

    // ... and nothing crashed on the way.
    await expect(page.getByText("Page could not render")).toHaveCount(0);
  });
});
