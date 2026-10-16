# Chmaba Cloud POS — native iOS app

A native iOS client for Chmaba Cloud POS, written in Swift/SwiftUI. It follows the
web POS in `apps/web` and the Android client in `apps/android`; the two are the
product reference, and `apps/android/DESIGN_GUIDE.md` is the shared design spec.

**Status: early.** Auth and the POS selling surface are being built. Most of the
Android client's screens do not exist here yet — see the parity matrix in
`docs/ios-platform-options.md` Appendix A.

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
- **ATS blocks cleartext HTTP by default.** Talking to a LAN dev server over plain
  `http://` needs an `NSAppTransportSecurity` exception in the Info.plist.
  **Not yet done.**

---

## API access

`APIConfig.baseURL` in `Data/APIClient.swift` is the single place to change:

```swift
static let baseURL = URL(string: "http://192.168.100.136/api/v1/")!
```

In the Docker dev stack, nginx (`front`) serves `/` and proxies `/api/` to the API
container. The API container itself has **no host port** — everything goes through
nginx on port 80.

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
    └── Screens/
        ├── LoginView.swift
        └── POSView.swift      # product grid, search, cart
```

### Deliberate differences from the Android client

- **Keychain, not `SharedPreferences`.** A POS device gets lost; the access token
  belongs in the platform's encrypted store.
- **`NavigationStack`, not a hand-rolled `BackHandler`.** The Android client
  maintains a bespoke nested unwind (`tab → moreDest → openOrder → …`); SwiftUI
  gives us that behaviour from a state enum.
- **Token refresh is coalesced.** The server rotates the refresh cookie, so a second
  concurrent refresh would invalidate the first. Refreshes share one in-flight task.

## Not built yet

- Checkout / `POST /orders` — the cart totals are computed but nothing is submitted
- Store currency (hard-coded USD) and tax rate (hard-coded 10%)
- Everything else in the Android parity matrix: inventory, purchasing, suppliers,
  reports, customers, categories, plans, settings
- Barcode scanning
- Offline behaviour
