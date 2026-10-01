// Cross-window bridge for the customer-facing display.
//
// The cashier POS window publishes a snapshot of the current order on a
// BroadcastChannel. The display window (opened with window.open at /display)
// subscribes to the same channel and never talks to the API, so it can run on a
// second monitor without its own session. A localStorage copy lets a display
// that is opened or reloaded later pick up the last known state.
//
// Store identity (name, logo, address) travels on the same channel as a separate
// "brand" message so a large logo data URL is only sent when it changes, rather
// than on every cart update.

export const DISPLAY_CHANNEL_NAME = "chmaba.customer-display";
export const DISPLAY_SNAPSHOT_KEY = "chmaba.customer-display.snapshot";
export const DISPLAY_BRAND_KEY = "chmaba.customer-display.brand";
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
  receiptPrinting = false,
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
    receiptPrinting: Boolean(receiptPrinting),
    updatedAt: Date.now(),
  };
}

/**
 * Store identity shown to the customer, so they know where they are paying.
 * `logo` is usually the store's receipt logo (a data URL).
 */
export function buildDisplayBrand({ name = "", logo = "", address = "" } = {}) {
  return {
    name: String(name || ""),
    logo: String(logo || ""),
    address: String(address || ""),
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

function readStored(key) {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

/**
 * POS-side link. `publish` fans the latest snapshot out to every display window
 * and `publishBrand` shares the store identity; a late-joining display that asks
 * for the current state gets both.
 */
export function createDisplayPublisher() {
  const channel = openChannel();
  let last = null;
  let lastBrand = null;
  const send = (message) => {
    try {
      channel?.postMessage({ source: DISPLAY_MESSAGE_SOURCE, ...message });
    } catch {
      /* ignore */
    }
  };
  if (channel) {
    channel.onmessage = (event) => {
      const data = event?.data;
      if (data?.source !== DISPLAY_MESSAGE_SOURCE || data?.type !== "request-state") return;
      if (last) send({ type: "snapshot", snapshot: last });
      if (lastBrand) send({ type: "brand", brand: lastBrand });
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
      send({ type: "snapshot", snapshot });
    },
    publishBrand(brand) {
      if (!brand) return;
      lastBrand = brand;
      try {
        window.localStorage.setItem(DISPLAY_BRAND_KEY, JSON.stringify(brand));
      } catch {
        /* ignore: an oversized logo must not break the order feed */
      }
      send({ type: "brand", brand });
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
 * from any connected POS) and again whenever the POS publishes. `onBrand`
 * receives the store identity and is optional.
 */
export function subscribeToDisplay(onSnapshot, onBrand) {
  if (typeof onSnapshot !== "function") return () => {};
  const hasBrandHandler = typeof onBrand === "function";

  const storedSnapshot = readStored(DISPLAY_SNAPSHOT_KEY);
  if (storedSnapshot) onSnapshot(storedSnapshot);
  const storedBrand = readStored(DISPLAY_BRAND_KEY);
  if (storedBrand && hasBrandHandler) onBrand(storedBrand);

  const channel = openChannel();
  if (channel) {
    channel.onmessage = (event) => {
      const data = event?.data;
      if (data?.source !== DISPLAY_MESSAGE_SOURCE) return;
      if (data.type === "snapshot" && data.snapshot) onSnapshot(data.snapshot);
      else if (data.type === "brand" && data.brand && hasBrandHandler) onBrand(data.brand);
    };
  }
  const onStorage = (event) => {
    if (!event.newValue) return;
    try {
      if (event.key === DISPLAY_SNAPSHOT_KEY) onSnapshot(JSON.parse(event.newValue));
      else if (event.key === DISPLAY_BRAND_KEY && hasBrandHandler) onBrand(JSON.parse(event.newValue));
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
