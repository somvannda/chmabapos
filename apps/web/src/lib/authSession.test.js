import test from "node:test";
import assert from "node:assert/strict";

import { isSessionExpired } from "./authSession.js";

test("treats a 401 on an authenticated request as a session expiry", () => {
  assert.equal(isSessionExpired(401, "stored-token"), true);
});

test("ignores a 401 without a token (e.g. a wrong password on sign-in)", () => {
  assert.equal(isSessionExpired(401, ""), false);
  assert.equal(isSessionExpired(401, undefined), false);
  assert.equal(isSessionExpired(401, null), false);
});

test("ignores non-401 responses", () => {
  assert.equal(isSessionExpired(403, "stored-token"), false);
  assert.equal(isSessionExpired(200, "stored-token"), false);
  assert.equal(isSessionExpired(500, "stored-token"), false);
});
