import { useCallback, useEffect, useState } from "react";

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

  useEffect(() => {
    const sync = () => setCart(readCart(storageKey));
    sync();
    window.addEventListener(CART_EVENT, sync);
    // Another tab changing the same cart also counts.
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(CART_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, [storageKey]);

  // Same signature the store page used to have locally, so every existing call site is
  // unchanged by moving the cart out of the component.
  const setQuantity = useCallback(
    (lineKey, delta) => {
      setCart((current) => {
        const next = applyDelta(current, lineKey, delta);
        writeCart(storageKey, next);
        return next;
      });
    },
    [storageKey],
  );

  return { cart, setQuantity, count: cartCount(cart) };
}
