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

## What prints silently

| Action | Where |
| --- | --- |
| Receipt after a completed sale | POS, when *Auto-print receipt* is on |
| Receipt for a past order | Orders list → **Print receipt** icon |
| Receipt from the preview | Orders list → **View receipt** → **Print receipt** |
| Z-report at shift close | POS shift report → **Print Z report** |

The preview button (**View receipt**) never prints by itself, so staff can check
an order on screen without wasting paper.

## Options

`start-pos.ps1` parameters:

| Parameter | Default | Description |
| --- | --- | --- |
| `-Url` | required | POS URL to open |
| `-Browser` | auto-detected Chrome/Edge | Full path to a Chromium browser executable |
| `-FullScreen` | off | Use `--kiosk` instead of an app window |
| `-UserDataDir` | `%LOCALAPPDATA%\ChmabaPOS\browser` | Isolated browser profile directory |

## Fallback without kiosk mode

If the POS is opened in a normal tab (no `--kiosk-printing`), everything still
works — receipts just go through the browser print dialog, where the operator
can pick the printer and confirm. No feature is lost.

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
