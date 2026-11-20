import { test } from "node:test";
import assert from "node:assert/strict";

import {
  createAnalytics,
  hashKey,
  isDeadClick,
  normalizeClientRoute,
  routeKeyFor,
  sanitizeProps,
  shouldSample,
} from "./analytics.js";

function memoryStorage() {
  const data = new Map();
  return {
    getItem: (key) => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => data.set(key, String(value)),
    removeItem: (key) => data.delete(key),
  };
}

function harness(overrides = {}) {
  const sent = [];
  const clock = { now: Date.parse("2026-11-20T08:00:00Z") };
  const analytics = createAnalytics({
    enabled: true,
    transport: (payload) => sent.push(JSON.parse(payload.body)),
    clock: () => clock.now,
    localStorageRef: memoryStorage(),
    sessionStorageRef: memoryStorage(),
    ...overrides,
  });
  return { analytics, sent, clock };
}

test("secrets and personal details never reach the payload", () => {
  const cleaned = sanitizeProps({
    password: "hunter2",
    access_token: "tok",
    phone: "+855123",
    email: "a@b.c",
    nested: { card_number: "4111", ok: 1 },
    step: 2,
  });
  assert.deepEqual(cleaned, { nested: { ok: 1 }, step: 2 });
});

test("routes lose their query, fragment and id-shaped segments", () => {
  assert.equal(normalizeClientRoute("/reset-password?token=SECRET#x"), "/reset-password");
  assert.equal(
    normalizeClientRoute("/0b6c2f1a-8f43-4c2e-9f4f-8f0f7a1b2c3d/setup/plan"),
    "/:id/setup/plan",
  );
  assert.equal(normalizeClientRoute("/order/0123456789abcdef0123456789abcdef"), "/order/:token");
  assert.equal(normalizeClientRoute(""), null);
});

test("route keys are stable and human-meaningful", () => {
  assert.equal(routeKeyFor({ kind: "user", view: "products" }), "products");
  assert.equal(routeKeyFor({ kind: "setup", step: "plan" }), "setup.plan");
  assert.equal(routeKeyFor({ kind: "public" }), "landing");
  assert.equal(routeKeyFor(null), "unknown");
});

test("an error is grouped by hash, never by its text", () => {
  const first = hashKey("TypeError: undefined is not a function");
  const second = hashKey("TypeError: undefined is not a function");
  assert.equal(first, second);
  assert.ok(first.startsWith("k"));
  assert.ok(!first.includes("TypeError"));
});

test("sampling is deterministic at the boundaries", () => {
  assert.equal(shouldSample(1, () => 0.99), true);
  assert.equal(shouldSample(0, () => 0), false);
  assert.equal(shouldSample(0.2, () => 0.1), true);
  assert.equal(shouldSample(0.2, () => 0.9), false);
});

test("a batch carries the session, the event and sanitized props", () => {
  const { analytics, sent } = harness();
  analytics.track("onboarding.step_viewed", { step: 1, password: "hunter2" });
  analytics.flush();

  assert.equal(sent.length, 1);
  const batch = sent[0];
  assert.equal(batch.source, "web");
  assert.equal(batch.events.length, 1);
  assert.equal(batch.events[0].name, "onboarding.step_viewed");
  assert.deepEqual(batch.events[0].props, { step: 1 });
  assert.ok(batch.session.id);
  assert.ok(batch.session.anonymous_id);
  assert.ok(!JSON.stringify(batch).includes("hunter2"));
});

test("a session rotates after thirty idle minutes", () => {
  const { analytics, clock } = harness();
  const first = analytics.session().id;
  clock.now += 31 * 60 * 1000;
  const second = analytics.session().id;
  assert.notEqual(first, second);
});

test("a page view closes the previous one with its dwell time", () => {
  const { analytics, sent, clock } = harness();
  analytics.page("/acme/products", "products");
  clock.now += 1500;
  analytics.page("/acme/settings", "settings");
  analytics.flush();

  const names = sent[0].events.map((event) => event.name);
  assert.deepEqual(names, ["page.viewed", "page.left", "page.viewed"]);
  const left = sent[0].events.find((event) => event.name === "page.left");
  assert.equal(left.props.route_key, "products");
  assert.equal(left.props.dwell_ms, 1500);
});

test("step timing is attached to the completion event", () => {
  const { analytics, sent, clock } = harness();
  analytics.startStep("onboarding.2");
  clock.now += 4200;
  analytics.endStep("onboarding.2", "onboarding.step_completed", { step: 2 });
  analytics.flush();

  assert.equal(sent[0].events[0].name, "onboarding.step_completed");
  assert.equal(sent[0].events[0].duration_ms, 4200);
});

test("a click that changed nothing is a dead click", () => {
  const before = { path: "/pos", resources: 4, dialog: false };
  assert.equal(isDeadClick(before, { ...before }), true);
  assert.equal(isDeadClick(before, { ...before, path: "/orders" }), false);
  assert.equal(isDeadClick(before, { ...before, resources: 5 }), false);
  assert.equal(isDeadClick(before, { ...before, dialog: true }), false);
  assert.equal(isDeadClick(null, before), false);
});

test("a disabled SDK sends nothing", () => {
  const { analytics, sent } = harness({ enabled: false });
  analytics.track("page.viewed", { route_key: "pos" });
  analytics.flush();
  assert.equal(sent.length, 0);
});
