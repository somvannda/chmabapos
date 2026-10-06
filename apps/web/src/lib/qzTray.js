// QZ Tray print transport (browser only).
//
// QZ Tray is a local service the page talks to over a websocket. This module
// wraps the globals QZ exposes behind the small `{ isAvailable, print }` adapter
// shape used by lib/printing.js, so the rest of the app never touches QZ
// directly. Everything is injectable — the QZ global, the script loader and the
// signing functions — which keeps it unit-testable without a real QZ install or
// a DOM.
//
// Silent printing requires signed messages. `sign` returns a signature for the
// request QZ hands us and `certificate` returns the PEM certificate; both come
// from the API in production (see docs/native-printing.md) and must never be a
// private key in the bundle. When either is omitted QZ is left to its own
// (unsigned) behaviour.

import { CASH_DRAWER_PULSE } from "./printing.js";

/** Base64-encode raw bytes, the form QZ expects for a raw print job. */
export function bytesToBase64(bytes) {
  const source = Array.isArray(bytes) ? bytes : [];
  const binary = source.map((byte) => String.fromCharCode(Number(byte) & 0xff)).join("");
  return btoa(binary);
}

/**
 * Inject the vendored QZ script once. Resolves as soon as the tag loads; the
 * caller still waits for `window.QZ` to appear. Rejects when there is no
 * document (e.g. during a server-side unit test).
 */
export function loadQzScript(scriptUrl, { doc = typeof document !== "undefined" ? document : null } = {}) {
  if (!doc) return Promise.reject(new Error("QZ Tray requires a browser document"));
  if (doc.querySelector(`script[data-qz-tray="${scriptUrl}"]`)) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const script = doc.createElement("script");
    script.src = scriptUrl;
    script.async = true;
    script.dataset.qzTray = scriptUrl;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Could not load ${scriptUrl}`));
    doc.head.appendChild(script);
  });
}

/**
 * Build the QZ adapter. `qz` (or `window.QZ`) is the QZ global; `loadScript` is
 * only used when the global is missing and a `scriptUrl` is set. The returned
 * `print` connects lazily, so a store that never prints through QZ never opens a
 * socket.
 */
export function createQzTransport({
  qz,
  scriptUrl = null,
  loadScript = loadQzScript,
  sign,
  certificate,
  resolveGlobal = () => (typeof window !== "undefined" ? window.QZ : undefined),
} = {}) {
  let lib = qz || null;
  let connecting = null;

  const current = () => lib || (lib = resolveGlobal() || null);

  async function connect() {
    let qzLib = current();
    if (!qzLib && scriptUrl) {
      await loadScript(scriptUrl);
      qzLib = current();
    }
    if (!qzLib) throw new Error("QZ Tray is not available");
    if (typeof certificate === "function") {
      qzLib.security.setCertificatePromise((resolve, reject) => {
        Promise.resolve().then(certificate).then(resolve, reject);
      });
    }
    if (typeof sign === "function") {
      qzLib.security.setSignaturePromise((toSign) => Promise.resolve().then(() => sign(toSign)));
    }
    if (!qzLib.websocket.isActive()) await qzLib.websocket.connect();
    return qzLib;
  }

  return {
    isAvailable() {
      const qzLib = current();
      try {
        return Boolean(qzLib && qzLib.websocket.isActive());
      } catch {
        return false;
      }
    },
    async print({ element, printer = null, cashDrawer = false } = {}) {
      if (!connecting) connecting = connect();
      const qzLib = await connecting.catch((error) => {
        connecting = null;
        throw error;
      });
      const target = printer || null;
      await qzLib.print({ type: "html", format: "plain", printer: target }, [element]);
      if (cashDrawer) {
        await qzLib.print({ type: "raw", format: "plain", printer: target }, [bytesToBase64(CASH_DRAWER_PULSE)]);
      }
      return { ok: true, printer: target, cashDrawer: Boolean(cashDrawer) };
    },
    connect,
  };
}
