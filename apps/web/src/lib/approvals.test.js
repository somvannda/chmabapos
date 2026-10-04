import test from "node:test";
import assert from "node:assert/strict";

import { isPendingApproval } from "./approvals.js";

test("detects a held-for-approval response", () => {
  assert.equal(isPendingApproval({ status: "pending_approval", approval_request: { id: "req-1" } }), true);
});

test("treats an executed result as not pending", () => {
  assert.equal(isPendingApproval({ id: "cust-1", points: 10 }), false);
  assert.equal(isPendingApproval({ product_id: "p1", on_hand: 1 }), false);
});

test("is safe for empty and non-object values", () => {
  assert.equal(isPendingApproval(null), false);
  assert.equal(isPendingApproval(undefined), false);
  assert.equal(isPendingApproval("pending_approval"), false);
  assert.equal(isPendingApproval(202), false);
});
