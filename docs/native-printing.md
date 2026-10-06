# Native printing via QZ Tray (planned)

> Status: **adapter + settings**. The transport planner
> (`apps/web/src/lib/printing.js`), the QZ adapter (`apps/web/src/lib/qzTray.js`)
> and the POS-preferences controls are in place, all covered by unit tests. The
> API signing endpoints and the register-side wiring are the remaining follow-ups
> tracked in issue #591.

## Why, when kiosk printing already works

`docs/printing.md` covers silent printing today: launch the POS with
`start-pos.ps1` and the browser prints with no dialog via `--kiosk-printing`.
That is the default and stays supported. It has real limits, though:

| Need | `--kiosk-printing` | QZ Tray |
| --- | --- | --- |
| No print dialog | yes | yes |
| Print to a **specific** printer per document | no — OS default / last used | yes |
| Cash-drawer kick | no | yes |
| Auto-cut / raw ESC/POS | no | yes |
| Works without a launcher shortcut | no | yes |
| macOS / Linux parity | unreliable | yes |
| No extra install per till | yes | no (Java + QZ service) |

QZ Tray is therefore the right choice when a store needs per-printer targeting or
the cash drawer. It is an **opt-in** print method, not a replacement.

## How it fits the existing code

Receipts are rendered into `.receipt-print-area` inside `.receipt-print-only` and
sent to the printer with `window.print()`. `apps/web/src/lib/printing.js` adds a
transport decision in front of that:

- `normalizePrintSettings(prefs)` reads the store preferences:
  - `print_method`: `"browser"` (default), `"kiosk"` or `"qz"`.
  - `print_printers`: `{ receipt, invoice, "z-report", test }` → printer names,
    per till. Empty means "use the OS/QZ default".
  - `print_cash_drawer`: boolean, opt-in.
  - `print_qz_script_url`: where the vendored `qz-tray.js` is served from
    (default `/vendor/qz-tray.js`).
- `planPrintJob({ document, prefs, qzAvailable, hasElement })` chooses `qz` only
  when the store selected it, the service answered and there is rendered markup
  to send; otherwise `browser`. The drawer pulse is planned **only** for
  `receipt`.
- `printDocument({ document, prefs, element, qz, fallback, onFallback })` runs the
  QZ job and, if it throws, runs the existing `window.print()` fallback and
  reports it through `onFallback`. A print failure never blocks a sale.

Callers (`workspace.jsx` `printOrderReceipt`, the print button in
`receipts.jsx`) will be routed through `printDocument` in the follow-up, keeping
today's behavior when `print_method` is `"browser"`.

## Print methods

| Setting | Behavior |
| --- | --- |
| `browser` (default) | Today's `window.print()`; dialog unless launched with `--kiosk-printing`. |
| `kiosk` | Same as `browser`; documents the intent to run under `start-pos.ps1`. |
| `qz` | QZ Tray; falls back to `browser` if the service is unreachable. |

## QZ Tray setup (per till)

1. Install the [QZ Tray](https://qz.io/) app (it bundles a Java runtime) on each
   register, and keep it running (it listens on `localhost:8181`).
2. Vendor the client script: copy `js/qz-tray.js` from the QZ install into
   `apps/web/public/vendor/qz-tray.js` so it is served from the POS origin
   (`/vendor/qz-tray.js`). Do **not** load it from a CDN.
3. In the POS: *Settings → POS preferences → Printing* choose **QZ Tray**, map
   each document to a printer, and optionally enable the cash drawer.

## Signing

QZ Tray requires signed messages for silent printing, and the signing private key
must never ship in the browser bundle. The page wires
`qz.security.setCertificatePromise` / `setSignaturePromise` to the API:

- `GET /printing/qz/certificate` → the public certificate.
- `POST /printing/qz/sign` → signs a QZ request payload.

The sign endpoint must validate that the payload is a QZ signing request (shape,
length, rate-limit) so it cannot be used as a general-purpose signing oracle.
`print_qz_script_url` lets a store point at a locally served copy if needed.

## Fallback

If QZ is not installed, not running, or throws, `printDocument` runs the browser
path and reports the failure so the POS can show a dismissible notice. Staff
never lose the ability to print.

## Spike checklist (before the full build)

- [ ] Connect from the POS origin and silently print rendered receipt HTML to a
      named printer.
- [ ] Confirm `https` page → `wss://localhost:8181` is not blocked as mixed
      content, and that QZ's self-signed cert is trusted.
- [ ] Prove the API signing round-trip against `setCertificatePromise` /
      `setSignaturePromise`.
- [ ] Prove the offline-QZ fallback.
- [ ] Confirm Khmer/bilingual shaping survives HTML rendering; decide whether raw
      ESC/POS is needed.
- [ ] Confirm QZ licensing covers silent printing/signing for our case.

## Open questions

- Backend store setting vs device-local for the printer map — printers are per
  till, so device-local is the likely default.
- Which QZ version/tier is required, and its licensing terms.
- Whether the first cut renders HTML (preserves Khmer) or raw ESC/POS.

## Non-goals

- Replacing `window.print()`; it stays the fallback.
- An Electron desktop shell (separate platform decision).
- Bundling or auto-installing the QZ Tray service from the repo.
