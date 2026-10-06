// Printing transport selection and job planning.
//
// Receipts print with window.print() today; silent output on Windows comes from
// launching the browser with --kiosk-printing (see docs/printing.md). This module
// adds a transport layer so a store can instead print through a local QZ Tray
// service, which targets a named printer, kicks the cash drawer and reuses the
// existing receipt markup without the launcher flag (see docs/native-printing.md).
//
// The module is dependency-free: the QZ adapter is injected by the caller, so the
// planning logic stays pure and testable, and the browser path is the default
// whenever QZ is not configured or not running. Printing must never block a sale,
// so any QZ failure degrades to window.print().

export const PRINT_METHOD = {
  BROWSER: "browser",
  KIOSK: "kiosk",
  QZ: "qz",
};

export const PRINT_DOCUMENT = {
  RECEIPT: "receipt",
  INVOICE: "invoice",
  Z_REPORT: "z-report",
  TEST: "test",
};

const DOCUMENT_KINDS = Object.values(PRINT_DOCUMENT);
const METHOD_KINDS = Object.values(PRINT_METHOD);

// Default QZ Tray script, served from the POS origin. The runbook in
// docs/native-printing.md explains how to vendor it from the QZ install.
export const DEFAULT_QZ_SCRIPT_URL = "/vendor/qz-tray.js";

// ESC/POS pulse that opens the cash drawer wired to the receipt printer
// (ESC p m t1 t2 — pin 0, 25 x 2ms on, 250 x 2ms off).
export const CASH_DRAWER_PULSE = [0x1b, 0x70, 0x00, 0x19, 0xfa];

/** Normalize the print-related store preferences into one shape with safe defaults. */
export function normalizePrintSettings(prefs = {}) {
  const source = prefs && typeof prefs === "object" ? prefs : {};
  const method = METHOD_KINDS.includes(source.print_method) ? source.print_method : PRINT_METHOD.BROWSER;
  const rawPrinters = source.print_printers && typeof source.print_printers === "object" ? source.print_printers : {};
  const printers = {};
  for (const document of DOCUMENT_KINDS) {
    const value = rawPrinters[document];
    printers[document] = typeof value === "string" && value.trim() ? value.trim() : null;
  }
  const scriptUrl = typeof source.print_qz_script_url === "string" && source.print_qz_script_url.trim()
    ? source.print_qz_script_url.trim()
    : DEFAULT_QZ_SCRIPT_URL;
  return {
    method,
    printers,
    cashDrawer: source.print_cash_drawer === true,
    scriptUrl,
  };
}

/** The printer configured for a document kind, or null to use the OS/QZ default. */
export function resolvePrinter(settings, document) {
  const normalized = settings && settings.printers ? settings : normalizePrintSettings(settings);
  return normalized.printers[document] || null;
}

/**
 * Decide how a document will print. QZ is used only when the store selected it,
 * the adapter reports it is reachable and there is a rendered element to send;
 * otherwise the browser path (window.print / kiosk) is used.
 */
export function planPrintJob({ document = PRINT_DOCUMENT.RECEIPT, prefs = {}, qzAvailable = false, hasElement = true } = {}) {
  const settings = normalizePrintSettings(prefs);
  const kind = DOCUMENT_KINDS.includes(document) ? document : PRINT_DOCUMENT.RECEIPT;
  if (settings.method === PRINT_METHOD.QZ && qzAvailable && hasElement) {
    return {
      document: kind,
      transport: PRINT_METHOD.QZ,
      printer: resolvePrinter(settings, kind),
      cashDrawer: settings.cashDrawer && kind === PRINT_DOCUMENT.RECEIPT,
    };
  }
  return { document: kind, transport: PRINT_METHOD.BROWSER, printer: null, cashDrawer: false };
}

/**
 * Print one document, preferring QZ Tray when planned and otherwise running the
 * caller's browser fallback. The QZ adapter is `{ isAvailable, print }`; a throw
 * from it degrades to the fallback rather than surfacing an error to the cashier.
 * Returns the plan plus `{ ok, error?, fallback? }` so callers can surface a
 * dismissible notice without blocking checkout.
 */
export async function printDocument({ document, prefs, element, qz, fallback, onFallback } = {}) {
  const available = Boolean(qz && (typeof qz.isAvailable === "function" ? qz.isAvailable() : qz.isAvailable));
  const plan = planPrintJob({ document, prefs, qzAvailable: available, hasElement: Boolean(element) });
  if (plan.transport === PRINT_METHOD.QZ) {
    try {
      await qz.print({ document: plan.document, element, printer: plan.printer, cashDrawer: plan.cashDrawer });
      return { ...plan, ok: true };
    } catch (error) {
      const result = typeof fallback === "function" ? await fallback() : undefined;
      if (typeof onFallback === "function") onFallback(error, plan);
      return { ...plan, transport: PRINT_METHOD.BROWSER, ok: false, error, fallback: result };
    }
  }
  const result = typeof fallback === "function" ? await fallback() : undefined;
  return { ...plan, ok: true, fallback: result };
}
