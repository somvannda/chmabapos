import test from "node:test";
import assert from "node:assert/strict";

import { expiryStatus } from "./batchExpiry.js";

test("expired batches are red and count days since", () => {
  assert.deepEqual(expiryStatus(-3), { label: "expired 3d ago", tone: "red" });
  assert.deepEqual(expiryStatus(-1), { label: "expired 1d ago", tone: "red" });
});

test("a batch expiring today is flagged", () => {
  assert.deepEqual(expiryStatus(0), { label: "expires today", tone: "yellow" });
});

test("future expiry counts down in days", () => {
  assert.deepEqual(expiryStatus(5), { label: "in 5d", tone: "yellow" });
});

test("a missing expiry date is neutral", () => {
  assert.deepEqual(expiryStatus(null), { label: "no expiry", tone: "neutral" });
  assert.deepEqual(expiryStatus(undefined), { label: "no expiry", tone: "neutral" });
});
