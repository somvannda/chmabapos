import test from "node:test";
import assert from "node:assert/strict";

import { createRefreshCoordinator } from "./refreshCoordinator.js";

test("shares one refresh while it is in flight", async () => {
  let calls = 0;
  let release;
  const refresh = () => {
    calls += 1;
    return new Promise((resolve) => {
      release = resolve;
    });
  };
  const coordinated = createRefreshCoordinator(refresh, { locks: null });

  const first = coordinated();
  const second = coordinated();
  assert.equal(first, second, "callers share the in-flight promise");
  // The coordinator defers the call by a microtask, so let it start first.
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(calls, 1, "a burst of 401s must trigger a single refresh");

  release("token");
  assert.equal(await first, "token");
  assert.equal(await second, "token");
});

test("allows a new refresh once the previous one settles", async () => {
  let calls = 0;
  const coordinated = createRefreshCoordinator(() => {
    calls += 1;
    return Promise.resolve(`token-${calls}`);
  }, { locks: null });

  assert.equal(await coordinated(), "token-1");
  assert.equal(await coordinated(), "token-2");
  assert.equal(calls, 2);
});

test("clears in-flight state after a failure so it can be retried", async () => {
  let calls = 0;
  const coordinated = createRefreshCoordinator(() => {
    calls += 1;
    return calls === 1 ? Promise.reject(new Error("expired")) : Promise.resolve("token");
  }, { locks: null });

  await assert.rejects(coordinated());
  assert.equal(await coordinated(), "token");
  assert.equal(calls, 2);
});

test("serializes refreshes across tabs that share the cookie jar", async () => {
  // A tiny stand-in for navigator.locks: callbacks run one after another.
  let tail = Promise.resolve();
  const locks = {
    request(_name, callback) {
      const result = tail.then(callback);
      tail = result.then(
        () => undefined,
        () => undefined,
      );
      return result;
    },
  };

  const order = [];
  let finishFirst;
  const firstTab = createRefreshCoordinator(
    () =>
      new Promise((resolve) => {
        order.push("first-start");
        finishFirst = () => {
          order.push("first-end");
          resolve("first-token");
        };
      }),
    { locks },
  );
  const secondTab = createRefreshCoordinator(
    () => {
      order.push("second-start");
      return Promise.resolve("second-token");
    },
    { locks },
  );

  const first = firstTab();
  const second = secondTab();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.deepEqual(order, ["first-start"], "the second tab waits for the first");

  finishFirst();
  assert.equal(await first, "first-token");
  assert.equal(await second, "second-token");
  assert.deepEqual(order, ["first-start", "first-end", "second-start"]);
});
