# Vendored client scripts

## `qz-tray.js`

The QZ Tray browser connector, served at `/vendor/qz-tray.js` and loaded on
demand by `apps/web/src/lib/qzTray.js` (`DEFAULT_QZ_SCRIPT_URL`). It is only
fetched when a store selects the **QZ Tray** print method, so stores that use the
browser/kiosk path never download it.

- **Package:** [`qz-tray`](https://www.npmjs.com/package/qz-tray)
- **Version:** 2.3.0
- **License:** LGPL-2.1-only (the SPDX header is preserved at the top of the file)
- **Source:** <https://registry.npmjs.org/qz-tray/-/qz-tray-2.3.0.tgz>

Do **not** load this from a CDN — it runs with access to the local QZ service.

### Updating

```powershell
$tmp = New-Item -ItemType Directory -Force "$env:TEMP\qz-tray"
Invoke-WebRequest "https://registry.npmjs.org/qz-tray/-/qz-tray-<version>.tgz" -OutFile "$tmp\qz-tray.tgz"
tar -xzf "$tmp\qz-tray.tgz" -C $tmp
Copy-Item "$tmp\package\qz-tray.js" apps/web/public/vendor/qz-tray.js -Force
```

Keep the version note above in step with the file. QZ Tray 2.1+ signs with
SHA-512; the API signing endpoints assume that (`QZ_PRINT_SIGNATURE_ALGORITHM`).
