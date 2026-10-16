# Chmaba Cloud POS — native iOS app

A native iOS client for Chmaba Cloud POS, written in Swift/SwiftUI. It follows the
web POS in `apps/web` and the Android client in `apps/android`; the two are the
product reference, and `apps/android/DESIGN_GUIDE.md` is the shared design spec.

**Status: every screen in the prototype's inventory now exists**, minus onboarding — see
"What exists now" below. The parity matrix in `docs/ios-platform-options.md` Appendix A is
older than this file and still describes an earlier state.

---

## How this is built (there is no Xcode)

This is an **xtool** project, not an Xcode project. It builds on Windows via WSL,
with no Mac involved:

```
WSL Ubuntu  →  Swift 6.4.1 + iOS 27 SDK (extracted from Xcode.xip)  →  xtool  →  iPhone
```

`xtool` bundles the SwiftPM library below into a signed `.app` and installs it over
USB. See `docs/ios-platform-options.md` for why this route was chosen and what it
costs.

### The one non-obvious piece: the USB relay

`xtool` installs fail over `usbipd` (USB/IP passthrough). Reads work; **every write
kills the connection** — reproduced with a plain 64 KB file, three times, from a
verified-good device state. The fix is to bypass USB/IP entirely and relay through
Apple's own Windows driver:

```
/var/run/usbmuxd  →  socat  →  <windows-host>:27015  →  Apple Mobile Device Service  →  iPhone
```

`libimobiledevice` **ignores `USBMUXD_SOCKET_ADDRESS`** (verified: zero TCP
connections made), but it always uses `/var/run/usbmuxd`. So the relay is published
at that exact path with `socat`, and `xtool` picks it up for free.

Requires, on the Windows side:

- `Apple Devices` installed from the Microsoft Store, and **launched once** — the
  package registers its driver/service on first run, not at install time
- a `netsh` portproxy forwarding `0.0.0.0:27015 → 127.0.0.1:27015` (persists across
  reboots by itself)
- a firewall rule allowing inbound TCP 27015

And in WSL, a systemd unit (`usbmux-relay.service`) running the `socat` bridge, with
the real `usbmuxd` masked so it cannot reclaim the socket.

**If `xtool dev` ever says "No device found", check the relay first:**

```bash
systemctl status usbmux-relay
```

Do not debug the Swift code — that failure is almost always the relay.

### Build and run

```bash
# in WSL, as root
cd /root/Chmaba/apps/ios        # or wherever the repo is mounted
xtool dev
```

First run compiles the Swift stdlib against the iOS SDK (minutes); after that it is
a few seconds.

### Constraints worth knowing

- **The provisioning profile expires every 7 days** on a free Apple ID. Re-run
  `xtool dev` to renew.
- **Google sign-in does not work here.** It needs the OAuth CSRF cookie and a
  redirect URI registered against `localhost`, which a device on the LAN cannot
  satisfy. Email/password only, for now. See `docs/ios-platform-options.md`
  Appendix B.
- **ATS allows cleartext HTTP to the LAN.** `Info.plist` carries the
  `NSAppTransportSecurity` exception, and **`NSLocalNetworkUsageDescription`** — without
  the latter, iOS 14+ blocks LAN requests and sign-in fails looking like a wrong password.

---

## API access

`APIConfig` in `Data/APIClient.swift` holds the address, and the app can change it at
runtime from the **Server** row on the sign-in screen — no rebuild needed. That matters,
because the right address depends on which network the phone is on.

**The one thing that breaks this, repeatedly: the API must bind a LAN interface.**

```bash
# right — reachable from the phone
python -m uvicorn app.main:app --app-dir chmabapos_api --host 0.0.0.0 --port 80

# wrong — binds 127.0.0.1 only, so the phone reaches nothing
python -m uvicorn app.main:app --app-dir chmabapos_api --port 8001
```

uvicorn defaults to **loopback** when `--host` is omitted, and the symptom is not an
obvious bind error: the phone shows a failed sign-in, which reads like a wrong password.
A firewall rule must also allow inbound TCP 80.

With the Docker dev stack, nginx (`front`) serves port 80 and proxies `/api/` to the API
container, so the container itself needs no host port. Either route works — the phone just
needs something listening on the machine's LAN address.

Two server-side details the client has to accommodate, both easy to get wrong:

1. **Money arrives as JSON strings.** `APIModel` in `chmabapos_api/app/schemas.py`
   sets no custom serialiser, so Pydantic v2 encodes `Decimal` as `"4.50"`, not
   `4.50`. A strict decoder fails the entire product list on the first price.
   `APIDecimal` accepts both forms.
2. **Dates carry microseconds.** FastAPI emits ISO-8601 with fractional seconds,
   which `ISO8601DateFormatter` rejects unless `.withFractionalSeconds` is set.
   `APIClient.decodeDate` tries both shapes.

---

## Layout

```
apps/ios/
├── Package.swift              # SwiftPM library — xtool packages exactly one product
├── xtool.yml                  # bundle ID
└── Sources/ChmabaPOS/
    ├── ChmabaPOSApp.swift     # @main, RootView, splash, brand mark
    ├── Data/
    │   ├── Models.swift       # DTOs mirroring chmabapos_api/app/schemas.py
    │   ├── APIClient.swift    # URLSession, cookie jar, coalesced token refresh
    │   └── SessionStore.swift # Keychain + signed-in state
    ├── Design/
    │   └── ChmabaTheme.swift  # colours/spacing from apps/android/DESIGN_GUIDE.md
    └── Screens/               # one file per destination; ShellView routes them
        ├── ShellView.swift    # bottom nav, More list, destination switch
        ├── DashboardView.swift
        ├── POSView.swift      # product grid, search, cart, payment, scan sheets
        ├── OrdersView.swift
        ├── ProductsView.swift
        ├── CustomersView.swift
        ├── InventoryView.swift
        ├── ReportsView.swift
        ├── PurchasingView.swift
        ├── SuppliersView.swift
        ├── CategoriesView.swift
        ├── ActivityView.swift
        ├── SettingsView.swift
        ├── TeamView.swift
        ├── HelpView.swift
        └── PlansView.swift
```

### Deliberate differences from the Android client

- **Keychain, not `SharedPreferences`.** A POS device gets lost; the access token
  belongs in the platform's encrypted store.
- **`NavigationStack`, not a hand-rolled `BackHandler`.** The Android client
  maintains a bespoke nested unwind (`tab → moreDest → openOrder → …`); SwiftUI
  gives us that behaviour from a state enum.
- **Token refresh is coalesced.** The server rotates the refresh cookie, so a second
  concurrent refresh would invalidate the first. Refreshes share one in-flight task.

## What exists now

Auth (login, signup, verify, reset), dashboard, POS with checkout, orders, products,
customers, inventory, reports, purchasing, suppliers, categories, activity, settings,
team, help and plans. **Every `MoreDestination` in `ShellView` has a real screen** — there
is no placeholder left, and the destination switch is exhaustive, so adding a case
without a screen is a compile error.

## Not built yet

- **Onboarding.** A newly registered account has no company or store, and
  `GET /workspaces/current` answers **403 "Set up a workspace before using this feature"**.
  The prototype's `setup-company` / `setup-questions` / `setup-plan` / `setup-ready`
  screens have no iOS equivalent, so a new customer cannot reach a usable store. This is
  the largest gap, and it affects every genuinely new customer.
- **Billing checkout.** `PlansView` shows live pricing and names the visible plan, but
  choosing one reports that the upgrade happens in the web app.
- **Tax rate** is hard-coded at 10%, matching the Android client's `TAX_RATE = 0.10`. The
  store's own rate is not read, so changing this is a cross-client change, not an iOS one.
- **Barcode scanning** — the scan sheet's camera tile is a placeholder.
- **Offline behaviour.**
- Customer detail, order detail and the product editor: their rows report the gap rather
  than opening nothing.

## Verifying without a device

Two checks run in the `iOS (apps/ios)` CI job, and neither needs Xcode:

- `scripts/verify-icons.sh` proves the Lucide icon port. It compiles this app's **real**
  `SVGPathParser` source on Linux against a `Path` that records geometry calls, renders all
  71 icons, and diffs that against a reference render of the same path data. Current
  result: `71 icons, 0 of 1577088 pixels differing`.
- `scripts/check-screen-contracts.py` asserts that every screen declaring `onBack` actually
  offers a way back. It exists because that defect once shipped on seven screens at once.

Neither of these renders a screen. Anything visual still has to be looked at on a device.

