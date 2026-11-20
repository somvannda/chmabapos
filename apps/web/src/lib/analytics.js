// First-party product telemetry for the merchant app.
//
// The collector is deliberately forgiving, the SDK is deliberately small: no
// dependency, no input values, no blocking request. Everything it sends is
// either a named funnel event or a click on a control the user can see.
//
// Rules that matter:
//  - Never read what the user typed. Clicks carry an element key/role, not a value.
//  - Never send a URL with a query or fragment: verification and reset links
//    carry `?token=`.
//  - Never break the app. Every storage/network/observer call is guarded, and a
//    failure is silent.
//
// See docs/onboarding-activation-analytics-plan.md.

const ANON_KEY = "chmaba.anon_id";
const SESSION_KEY = "chmaba.analytics_session";
const QUEUE_KEY = "chmaba.analytics_queue";
const TOKEN_KEY = "chmaba.access_token";
const SESSION_IDLE_MS = 30 * 60 * 1000;
const BATCH_SIZE = 20;
const FLUSH_MS = 5000;
const MAX_QUEUE = 200;

const SENSITIVE = /password|passcode|token|secret|api_key|authorization|card|cvv|cvc|otp|phone|email|full_name|address|qr_string|aba_payway_link|^code$/i;
const UUID_RE = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;
const LONG_HEX_RE = /\b[0-9a-f]{16,}\b/gi;

export function sanitizeProps(value, depth = 0) {
  if (depth > 2 || value == null || typeof value !== "object") return {};
  const cleaned = {};
  for (const [key, item] of Object.entries(value)) {
    if (!key || SENSITIVE.test(key)) continue;
    const name = key.slice(0, 80);
    if (item == null || typeof item === "boolean" || typeof item === "number") {
      cleaned[name] = item;
    } else if (typeof item === "string") {
      cleaned[name] = item.slice(0, 200);
    } else if (Array.isArray(item)) {
      cleaned[name] = item.slice(0, 20).map((entry) => (typeof entry === "object" ? null : String(entry).slice(0, 200)));
    } else {
      cleaned[name] = sanitizeProps(item, depth + 1);
    }
  }
  return cleaned;
}

// A path, never a URL: query and fragment are dropped before ids are masked.
export function normalizeClientRoute(path) {
  if (!path) return null;
  const clean = String(path).split("#")[0].split("?")[0].trim();
  if (!clean) return null;
  return clean.replace(UUID_RE, ":id").replace(LONG_HEX_RE, ":token").slice(0, 200);
}

// Route keys are stable and contain no ids or slugs, so a dashboard can group
// them. The username segment in `/<user>/products` is the merchant's own name.
export function routeKeyFor(route) {
  if (!route || typeof route !== "object") return "unknown";
  if (route.kind === "user" || route.kind === "legacy-user") return route.view || "dashboard";
  if (route.kind === "setup") return `setup.${route.step || "company"}`;
  if (route.kind === "order") return "public_order";
  if (route.kind === "display") return "customer_display";
  if (route.kind === "guides") return "guides";
  if (["login", "signup", "reset-password", "privacy", "terms", "contact", "refund-policy"].includes(route.kind)) return route.kind;
  if (route.kind === "public") return "landing";
  return route.kind || "unknown";
}

// A stable hash so a JavaScript error can be grouped without shipping its text
// (which may include a token or an email).
export function hashKey(value) {
  let hash = 5381;
  const text = String(value || "");
  for (let index = 0; index < text.length; index += 1) {
    hash = ((hash << 5) + hash + text.charCodeAt(index)) | 0;
  }
  return `k${(hash >>> 0).toString(36)}`;
}

export function shouldSample(rate, random = Math.random) {
  if (rate >= 1) return true;
  if (rate <= 0) return false;
  return random() < rate;
}

function uuid() {
  try {
    if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  } catch {
    /* ignore */
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (char) => {
    const value = (Math.random() * 16) | 0;
    const next = char === "x" ? value : (value & 0x3) | 0x8;
    return next.toString(16);
  });
}

function readStorage(storage, key) {
  try {
    return storage?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

function writeStorage(storage, key, value) {
  try {
    storage?.setItem(key, value);
  } catch {
    /* private mode / quota: telemetry is best-effort */
  }
}

function readToken() {
  if (typeof window === "undefined") return "";
  return (
    readStorage(window.localStorage, TOKEN_KEY) ||
    readStorage(window.sessionStorage, TOKEN_KEY) ||
    ""
  );
}

function readUtm() {
  if (typeof window === "undefined") return {};
  try {
    const params = new URLSearchParams(window.location.search);
    const utm = {};
    for (const key of ["source", "medium", "campaign", "content", "term"]) {
      const value = params.get(`utm_${key}`);
      if (value) utm[key] = value.slice(0, 120);
    }
    return utm;
  } catch {
    return {};
  }
}

function defaultTransport({ endpoint, body, token, beacon }) {
  if (beacon && typeof navigator !== "undefined" && navigator.sendBeacon) {
    try {
      navigator.sendBeacon(endpoint, new Blob([body], { type: "application/json" }));
      return;
    } catch {
      /* fall through to fetch */
    }
  }
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  fetch(endpoint, { method: "POST", headers, body, keepalive: true }).catch(() => {});
}

export function createAnalytics(options = {}) {
  const {
    endpoint = "/api/v1/telemetry/events",
    enabled = true,
    appVersion = "",
    transport = defaultTransport,
    clock = () => Date.now(),
    random = Math.random,
    localStorageRef = typeof window !== "undefined" ? window.localStorage : null,
    sessionStorageRef = typeof window !== "undefined" ? window.sessionStorage : null,
    documentRef = typeof document !== "undefined" ? document : null,
    windowRef = typeof window !== "undefined" ? window : null,
  } = options;

  let queue = [];
  let timer = null;
  let lastPage = null;
  let currentRouteKey = "unknown";
  let stepStarted = {};
  let rage = { key: "", count: 0, at: 0 };

  function anonymousId() {
    let value = readStorage(localStorageRef, ANON_KEY);
    if (!value) {
      value = uuid();
      writeStorage(localStorageRef, ANON_KEY, value);
    }
    return value;
  }

  function session() {
    const now = clock();
    let current = null;
    try {
      current = JSON.parse(readStorage(sessionStorageRef, SESSION_KEY) || "null");
    } catch {
      current = null;
    }
    if (!current || !current.id || now - Number(current.last || 0) > SESSION_IDLE_MS) {
      const utm = readUtm();
      current = {
        id: uuid(),
        anonymous_id: anonymousId(),
        started_at: new Date(now).toISOString(),
        entry_route: documentRef ? normalizeClientRoute(documentRef.location?.pathname) : null,
        referrer_host: documentRef?.referrer ? safeHost(documentRef.referrer) : null,
        utm,
        last: now,
      };
    }
    current.last = now;
    writeStorage(sessionStorageRef, SESSION_KEY, JSON.stringify(current));
    return current;
  }

  function enqueue(name, props, extra = {}) {
    if (!enabled || !name) return;
    queue.push({
      id: uuid(),
      name,
      occurred_at: new Date(clock()).toISOString(),
      route: extra.route ?? (documentRef ? normalizeClientRoute(documentRef.location?.pathname) : null),
      route_key: extra.route_key ?? currentRouteKey,
      element_key: extra.element_key,
      duration_ms: extra.duration_ms,
      props: sanitizeProps(props),
    });
    if (queue.length >= BATCH_SIZE) {
      flush();
      return;
    }
    if (!timer) timer = setTimeout(() => flush(), FLUSH_MS);
  }

  function flush({ beacon = false } = {}) {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    if (!enabled || queue.length === 0) return;
    const batch = queue.splice(0, BATCH_SIZE);
    const current = session();
    transport({
      endpoint,
      token: readToken(),
      beacon,
      body: JSON.stringify({
        source: "web",
        app_version: appVersion,
        sent_at: new Date(clock()).toISOString(),
        session: {
          id: current.id,
          anonymous_id: current.anonymous_id,
          started_at: current.started_at,
          entry_route: current.entry_route,
          referrer_host: current.referrer_host,
          utm: current.utm,
          platform: "web",
          locale: typeof navigator !== "undefined" ? navigator.language : null,
          timezone: safeTimeZone(),
        },
        events: batch,
      }),
    });
    saveQueue();
    if (queue.length) timer = setTimeout(() => flush(), 0);
  }

  function persistentQueue() {
    try {
      const stored = JSON.parse(readStorage(localStorageRef, QUEUE_KEY) || "[]");
      return Array.isArray(stored) ? stored.slice(-MAX_QUEUE) : [];
    } catch {
      return [];
    }
  }

  function saveQueue() {
    writeStorage(localStorageRef, QUEUE_KEY, JSON.stringify(queue.slice(-MAX_QUEUE)));
  }

  function page(path, routeKey) {
    const nextKey = routeKey || currentRouteKey;
    if (lastPage) {
      enqueue("page.left", { route_key: lastPage.routeKey, dwell_ms: Math.max(clock() - lastPage.at, 0) });
    }
    currentRouteKey = nextKey;
    lastPage = { routeKey: nextKey, at: clock() };
    enqueue("page.viewed", { route_key: nextKey, title_key: nextKey }, { route: normalizeClientRoute(path) });
  }

  function track(name, props) {
    enqueue(name, props);
  }

  function startStep(key) {
    stepStarted[key] = clock();
  }

  function endStep(key, name, props) {
    const started = stepStarted[key];
    delete stepStarted[key];
    enqueue(name, props, { duration_ms: started ? Math.max(clock() - started, 0) : undefined });
  }

  function onClick(event) {
    const target = event.target?.closest?.('[data-track],button,a,[role="button"],[role="tab"],input[type="checkbox"]');
    if (!target) return;
    const label = (target.getAttribute("data-track") || target.getAttribute("aria-label") || target.getAttribute("name") || "").trim().slice(0, 60);
    const elementKey = target.getAttribute("data-track") || `${target.tagName.toLowerCase()}:${label}`;
    const now = clock();
    if (rage.key === elementKey && now - rage.at < 1000) {
      rage.count += 1;
      if (rage.count === 3) enqueue("ui.rage_click", { element_key: elementKey, clicks: rage.count });
    } else {
      rage = { key: elementKey, count: 1, at: now };
    }
    enqueue("ui.click", { element_key: elementKey, role: target.tagName.toLowerCase() });
  }

  function onError(event) {
    const message = event?.error?.stack || event?.message || "unknown";
    enqueue("error.client", { error_key: hashKey(message), boundary: "window" });
  }

  function onRejection(event) {
    enqueue("error.client", { error_key: hashKey(event?.reason?.stack || event?.reason?.message || "rejection"), boundary: "promise" });
  }

  function onHidden() {
    if (documentRef?.visibilityState === "hidden") flush({ beacon: true });
  }

  function init() {
    if (!enabled) return;
    const restored = persistentQueue();
    if (restored.length) queue = restored;
    session();
    if (windowRef) {
      windowRef.addEventListener("click", onClick, true);
      windowRef.addEventListener("error", onError);
      windowRef.addEventListener("unhandledrejection", onRejection);
      windowRef.addEventListener("pagehide", () => flush({ beacon: true }));
      documentRef?.addEventListener?.("visibilitychange", onHidden);
      setInterval(() => {
        if (documentRef?.visibilityState === "visible") enqueue("session.heartbeat", {}, {});
      }, 30000);
    }
    flush();
    saveQueue();
  }

  return { init, page, track, startStep, endStep, flush, session, setRouteKey: (key) => { currentRouteKey = key; } };
}

function safeHost(url) {
  try {
    return new URL(url).hostname.slice(0, 200);
  } catch {
    return null;
  }
}

function safeTimeZone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null;
  } catch {
    return null;
  }
}

function envValue(key, fallback) {
  try {
    return import.meta.env?.[key] ?? fallback;
  } catch {
    return fallback;
  }
}

const enabledFlag = String(envValue("VITE_ANALYTICS_ENABLED", "true")).toLowerCase() !== "false";
const apiBase = String(
  envValue("VITE_API_URL", "") || (typeof window !== "undefined" ? `${window.location.origin}/api/v1` : ""),
).replace(/\/$/, "");

export const analytics = createAnalytics({
  endpoint: `${apiBase}/telemetry/events`,
  enabled: enabledFlag,
  appVersion: envValue("VITE_APP_VERSION", ""),
});
