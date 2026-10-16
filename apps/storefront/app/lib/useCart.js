import { useCallback, useEffect, useRef, useState } from "react";

import { CART_EVENT, applyDelta, cartCount, readCart, writeCart } from "./cart";

/**
 * The cart for one store, shared between the store page and a product page.
 *
 * State starts empty on every render path, including the server, and fills in from
 * storage after mount. Reading storage in the initial state would make the client's
 * first render disagree with the server's markup, which React reports as a hydration
 * mismatch - and the cart arriving a moment later is invisible next to that.
 */
export function useCart(storageKey) {
  const [cart, setCart] = useState({});

  // The latest cart, so a handler can work out the next value without doing the work
  // inside a state updater. Updaters must be pure: React is free to call one more than
  // once - StrictMode does exactly that in development - so anything with an effect
  // beyond returning the new state (writing storage, dispatching an event) happens more
  // than once as well. That is what turned two taps of "add" into three items in the
  // browser tests, which run against the dev server where StrictMode is on, while a
  // production build looked perfectly correct.
  const latest = useRef({});

  useEffect(() => {
    const sync = () => {
      const stored = readCart(storageKey);
      latest.current = stored;
      setCart(stored);
    };
    sync();
    window.addEventListener(CART_EVENT, sync);
    // Another tab changing the same cart also counts.
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(CART_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, [storageKey]);

  // One place that updates state and storage together, called from event handlers
  // rather than from inside an updater.
  const commit = useCallback(
    (next) => {
      // Updated synchronously so two taps in the same tick compound rather than
      // both starting from the same stale value.
      latest.current = next;
      setCart(next);
      writeCart(storageKey, next);
    },
    [storageKey],
  );

  // Same signature the store page used to have locally, so every existing call site is
  // unchanged by moving the cart out of the component.
  const setQuantity = useCallback(
    (lineKey, delta) => commit(applyDelta(latest.current, lineKey, delta)),
    [commit],
  );

  // Empties the cart, for after an order is placed.
  const clear = useCallback(() => commit({}), [commit]);

  return { cart, setQuantity, clear, count: cartCount(cart) };
}
