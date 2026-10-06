# Silent receipt printing

The POS prints receipts, order copies and Z-reports with `window.print()`. A
normal browser tab always shows a print dialog first. To print **without a
dialog**, launch the POS with the browser's `--kiosk-printing` flag.

This works with any printer that Windows already has installed (thermal,
laser, network, shared) and keeps full Khmer/bilingual rendering, because the
browser still does the layout. No extra software is required.

## Setup (Windows)

1. **Choose the receipt printer.** Install it, and set it as the Windows
   *default* printer — kiosk printing sends pages to the default printer. If you
   prefer a different one, open one normal print dialog and select it; the
   browser remembers the last used printer.
2. **Launch the POS with the helper script** from the repo root:

   ```powershell
   # Production
   powershell -ExecutionPolicy Bypass -File .\start-pos.ps1 -Url https://chmaba.com/<store>/pos

   # Local development
   powershell -ExecutionPolicy Bypass -File .\start-pos.ps1 -Url http://localhost:5173

   # Full-screen kiosk (no window chrome, no address bar)
   powershell -ExecutionPolicy Bypass -File .\start-pos.ps1 -Url http://localhost:5173 -FullScreen

   # Also open the customer display on the second monitor
   powershell -ExecutionPolicy Bypass -File .\start-pos.ps1 -Url https://chmaba.com/<store>/pos -WithDisplay
   ```

   The script finds Chrome or Edge, opens the POS in an app window, and enables
   `--kiosk-printing`. It uses a dedicated browser profile
   (`%LOCALAPPDATA%\ChmabaPOS\browser`) so normal browsing is unaffected.

3. **Enable auto-print (optional).** In *Settings → POS preferences* turn on
   **Auto-print receipt**. Every completed sale then prints immediately with no
   preview and no dialog.

### Tip: pin it to the desktop

Create a shortcut with a target like:

```
"C:\Program Files\Google\Chrome\Application\chrome.exe" --kiosk-printing --user-data-dir="%LOCALAPPDATA%\ChmabaPOS\browser" --app=https://chmaba.com/<store>/pos
```

## Customer display on a second screen

POS devices with two screens can show the customer what is being sold, and the
KHQR code to scan, without mirroring the cashier's screen. The app serves this as
a separate `/display` page, and the POS window publishes the order to it over
`BroadcastChannel`.

Launch both windows together:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-pos.ps1 -Url https://chmaba.com/<store>/pos -WithDisplay
```

`-WithDisplay` derives the display URL as `<origin>/display` and opens it as a
second window of the **same browser profile** — required, because the display
listens on that profile's `BroadcastChannel`. It targets the second monitor
(`-DisplayScreen 2`) and can run full-screen with `-DisplayFullScreen`:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-pos.ps1 -Url https://chmaba.com/<store>/pos -WithDisplay -DisplayFullScreen
```

Chromium may ignore the requested position when it reuses a running browser
instance; if the window opens on the wrong monitor, drag it there once. You can
also open the display by hand at any time from the register with
**Open customer display**.

The display is optional per store — turn it off in *Settings → POS preferences →
Customer display*.

## What prints silently

| Action | Where |
| --- | --- |
| Receipt after a completed sale | POS, when *Auto-print receipt* is on |
| Receipt for a past order | Orders list → **Print receipt** icon |
| Receipt from the preview | Orders list → **View receipt** → **Print receipt** |
| Z-report at shift close | POS shift report → **Print Z report** |

The preview button (**View receipt**) never prints by itself, so staff can check
an order on screen without wasting paper.

## Item detail on receipts

Each receipt item line can print extra detail, controlled in
*Settings → Receipts → Item details on receipt*:

| Switch | Prints |
| --- | --- |
| Show item name | the product name on each line |
| Show SKU | the product or variant SKU, e.g. `MACBOOK-PRO13-32-512` |
| Show variant | the variant, e.g. `8GB/256GB · Midnight` |
| Show spec & color | labeled attributes stored on the product or variant, one per line, e.g. `Color: Midnight` |
| Show serial numbers | the serial / IMEI of every sold unit on the line |

Each detail only appears when the product actually has it, so simple products
are unchanged. All five default to on and apply to **both** the Classic
(thermal 80mm) and Professional (A5/A4) templates. On a narrow thermal receipt,
turn off the fields you do not need to keep each item line short. The details
are snapshotted onto the order line at sale time, so a reprint months later
still shows exactly what was sold.

## Options

`start-pos.ps1` parameters:

| Parameter | Default | Description |
| --- | --- | --- |
| `-Url` | required | POS URL to open |
| `-Browser` | auto-detected Chrome/Edge | Full path to a Chromium browser executable |
| `-FullScreen` | off | Use `--kiosk` instead of an app window |
| `-WithDisplay` | off | Also open the customer display window |
| `-DisplayUrl` | `<origin>/display` | Customer display URL (only used with `-WithDisplay` or when set) |
| `-DisplayScreen` | `2` | 1-based monitor for the customer display (1 = primary) |
| `-DisplayFullScreen` | off | Open the customer display full-screen |
| `-UserDataDir` | `%LOCALAPPDATA%\ChmabaPOS\browser` | Isolated browser profile directory |

## Fallback without kiosk mode

If the POS is opened in a normal tab (no `--kiosk-printing`), everything still
works — receipts just go through the browser print dialog, where the operator
can pick the printer and confirm. No feature is lost.

## Native printing with QZ Tray (planned)

The kiosk method above is the default and needs no extra software. For per-printer
targeting (receipt vs invoice vs Z-report) or a cash-drawer kick, a **QZ Tray**
transport is being added as an opt-in print method; see
[`native-printing.md`](native-printing.md). It falls back to `window.print()`
whenever QZ is not running, so nothing here stops working.

## Troubleshooting

- **Nothing prints.** Check that a default printer is set in Windows and that
  the browser was started by `start-pos.ps1` (look for `--kiosk-printing` in the
  shortcut target).
- **Wrong printer.** Set the receipt printer as Windows default, or print once
  through a normal dialog and select it; kiosk printing reuses that choice.
- **Blank page.** A receipt only prints if a receipt/order is on screen. Use the
  **Print receipt** action, or enable *Auto-print receipt* for sales.
- **Edge instead of Chrome.** Both work; force one with
  `-Browser "C:\Program Files\Microsoft\Edge\Application\msedge.exe"`.
