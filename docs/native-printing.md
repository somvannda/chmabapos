# Native printing via QZ Tray (opt-in)

> Status: **complete pending the live spike**. The transport planner
> (`apps/web/src/lib/printing.js`), the QZ adapter (`apps/web/src/lib/qzTray.js`),
> the POS-preferences controls, the API signing endpoints, the register wiring,
> the seeded help article and the vendored `qz-tray.js` client are all in place.
> The only remaining step is validating a real QZ Tray install, tracked in
> issue #591.

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

The register prints every sheet through `printDocument`. `printViaSheet` in
`workspace.jsx` sets the print order, then hands the rendered
`.receipt-print-only .receipt-print-area` element to `printDocument`, which uses
QZ when the store selected it and otherwise runs the same `window.print()`
fallback. `qzTransport` builds the adapter once and points its `certificate` /
`sign` callbacks at the API endpoints, so today's behavior is unchanged when
`print_method` is `"browser"`.

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
must never ship in the browser bundle. The API holds it:

- `GET /api/v1/printing/qz/certificate` → the public certificate (`text/plain`).
- `POST /api/v1/printing/qz/sign` with `{ "request": "<QZ request string>" }` →
  `{ "signature": "<base64>", "algorithm": "SHA512" }`.

Both require an authenticated operator. The signature is RSA PKCS#1 v1.5 over
SHA-512, base64-encoded, matching <https://qz.io/docs/signing>. The sign endpoint
bounds the payload size and the per-operator request rate so it cannot be used as
a general-purpose signing oracle.

Configure the key material on the server (never in the bundle):

| Setting | Meaning |
| --- | --- |
| `QZ_PRINT_CERTIFICATE_PATH` | Path to `digital-certificate.txt` (x509). |
| `QZ_PRINT_PRIVATE_KEY_PATH` | Path to the PKCS#8 `private-key.pem` (2048-bit RSA). |
| `QZ_PRINT_SIGNATURE_ALGORITHM` | Default `SHA512` (`SHA1` only for QZ Tray 2.0 and older). |
| `QZ_PRINT_REQUEST_MAX_BYTES` | Largest request string that will be signed (default 16384). |
| `QZ_PRINT_SIGN_RATE_LIMIT_PER_MINUTE` | Per-operator signing cap (default 120). |

When the two paths are unset the endpoints return `503` and the POS keeps its
browser/kiosk fallback. `print_qz_script_url` lets a store point at a locally
served copy of `qz-tray.js` if needed.

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
