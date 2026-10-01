// Cross-window bridge for the customer-facing display.
//
// The cashier POS window publishes a snapshot of the current order on a
// BroadcastChannel. The display window (opened with window.open at /display)
// subscribes to the same channel and never talks to the API, so it can run on a
// second monitor without its own session. A localStorage copy lets a display
// that is opened or reloaded later pick up the last known state.

export const DISPLAY_CHANNEL_NAME = "chmaba.customer-display";
export const DISPLAY_SNAPSHOT_KEY = "chmaba.customer-display.snapshot";
export const DISPLAY_MESSAGE_SOURCE = "chmaba-customer-display";

export const DISPLAY_STATUS = {
  IDLE: "idle",
  CART: "cart",
  PAYMENT: "payment",
  PAID: "paid",
};

/** Normalize one cart line for the display. */
function normalizeItem(item) {
  const quantity = Math.max(0, Number(item?.quantity) || 0);
  const unitPrice = Number(item?.unitPrice ?? item?.price) || 0;
  return {
    key: String(item?.key ?? item?.lineKey ?? item?.id ?? ""),
    name: String(item?.name ?? ""),
    quantity,
    unitPrice,
    lineTotal: Number((unitPrice * quantity).toFixed(2)),
  };
}

/**
 * Build the immutable snapshot the display renders. Pure apart from the
 * timestamp, so the shape can be unit-tested without a browser.
 */
export function buildDisplaySnapshot({
  storeName = "",
  currency = "USD",
  items = [],
  subtotal = 0,
  discount = 0,
  tax = 0,
  taxLabel = "Tax",
  tip = 0,
  total = 0,
  status = DISPLAY_STATUS.IDLE,
  payment = null,
  orderNumber = null,
} = {}) {
  const lines = (Array.isArray(items) ? items : []).map(normalizeItem);
  return {
    storeName: String(storeName || ""),
    currency: String(currency || "USD"),
    items: lines,
    itemCount: lines.reduce((count, line) => count + line.quantity, 0),
    subtotal: Number(subtotal) || 0,
    discount: Number(discount) || 0,
    tax: Number(tax) || 0,
    taxLabel: String(taxLabel || "Tax"),
    tip: Number(tip) || 0,
    total: Number(total) || 0,
    status,
    payment: payment
      ? {
          qrString: String(payment.qrString || ""),
          amount: Number(payment.amount) || 0,
          currency: String(payment.currency || currency || "USD"),
          externalId: payment.externalId ? String(payment.externalId) : null,
        }
      : null,
    orderNumber: orderNumber ? String(orderNumber) : null,
    updatedAt: Date.now(),
  };
}

function openChannel() {
  try {
    if (typeof BroadcastChannel === "function") return new BroadcastChannel(DISPLAY_CHANNEL_NAME);
  } catch {
    /* private mode or unsupported */
  }
  return null;
}

function readStoredSnapshot() {
  try {
    const raw = window.localStorage.getItem(DISPLAY_SNAPSHOT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

/**
 * POS-side link. `publish` fans the latest snapshot out to every display window
 * and answers late-joining displays that ask for the current state.
 */
export function createDisplayPublisher() {
  const channel = openChannel();
  let last = null;
  if (channel) {
    channel.onmessage = (event) => {
      const data = event?.data;
      if (last && data?.source === DISPLAY_MESSAGE_SOURCE && data?.type === "request-state") {
        try {
          channel.postMessage({ source: DISPLAY_MESSAGE_SOURCE, type: "snapshot", snapshot: last });
        } catch {
          /* ignore */
        }
      }
    };
  }
  return {
    publish(snapshot) {
      if (!snapshot) return;
      last = snapshot;
      try {
        window.localStorage.setItem(DISPLAY_SNAPSHOT_KEY, JSON.stringify(snapshot));
      } catch {
        /* ignore */
      }
      try {
        channel?.postMessage({ source: DISPLAY_MESSAGE_SOURCE, type: "snapshot", snapshot });
      } catch {
        /* ignore */
      }
    },
    close() {
      try {
        channel?.close();
      } catch {
        /* ignore */
      }
    },
  };
}

/**
 * Display-side link. Delivers the current state right away (from storage, then
 * from any connected POS) and again whenever the POS publishes. Returns an
 * unsubscribe function.
 */
export function subscribeToDisplay(onSnapshot) {
  if (typeof onSnapshot !== "function") return () => {};
  const stored = readStoredSnapshot();
  if (stored) onSnapshot(stored);

  const channel = openChannel();
  if (channel) {
    channel.onmessage = (event) => {
      const data = event?.data;
      if (data?.source === DISPLAY_MESSAGE_SOURCE && data?.type === "snapshot" && data.snapshot) {
        onSnapshot(data.snapshot);
      }
    };
  }
  const onStorage = (event) => {
    if (event.key !== DISPLAY_SNAPSHOT_KEY || !event.newValue) return;
    try {
      onSnapshot(JSON.parse(event.newValue));
    } catch {
      /* ignore */
    }
  };
  window.addEventListener("storage", onStorage);
  try {
    channel?.postMessage({ source: DISPLAY_MESSAGE_SOURCE, type: "request-state" });
  } catch {
    /* ignore */
  }
  return () => {
    window.removeEventListener("storage", onStorage);
    try {
      channel?.close();
    } catch {
      /* ignore */
    }
  };
}
