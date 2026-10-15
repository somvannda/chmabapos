# iOS app: platform options (and the Android parity baseline)

**Status:** decision doc — nothing built yet
**Date:** 2026-10-15
**Related:** `apps/android/README.md`, `apps/android/DESIGN_GUIDE.md`,
`docs/offline-mode-plan.md`, `docs/architecture.md`

---

## TL;DR

We have a mature **native Android** client (`apps/android`, ~9,900 lines of Kotlin +
Jetpack Compose) and **no iOS code anywhere in the repo**. iOS is not started, not
planned, and not mentioned.

iOS cannot be *run* on Windows — there is no simulator and no Xcode, and there is no
legitimate workaround. It can be *built* on Windows only via a remote/cloud Mac or
`xtool` (a community SwiftPM-based Xcode replacement that works in WSL). Note that
**`xtool` forces Swift**, which would mean writing a third codebase instead of reusing
the Kotlin app.

**The main argument for `xtool` does not apply to this repository.** It is **public**,
and standard GitHub-hosted runners are free for public repositories — **including
macOS** (§2.1). A `macos-latest` job gives us real Xcode, a simulator, previews,
Instruments and a working App Store path for **$0**. `xtool` exists to avoid paying for
a Mac; here there is nothing to avoid, so it buys us the *worst* development
experience in the list in exchange for nothing.

**Recommendation:**

1. **Before writing any iOS code, confirm the demand** (do stores actually ask for
   iPads/iPhones?). Native iOS is a second codebase we must maintain forever.
2. If the answer is *yes*, go with **Kotlin Multiplatform / Compose Multiplatform**
   (maximises reuse of the 9,900-line Android investment) and build it on a
   `macos-latest` runner. At our scale that runner is free.
3. If the answer is *maybe*, prove the loop before committing — but do it on the
   **free macOS runner**, not with `xtool`. Keep `xtool` only for a developer who
   specifically wants a Windows-only loop (Option A).
4. **Never** plan to release without macOS in the loop. App Store Connect upload is
   the one step with no supported non-Mac path — and here macOS is free anyway.

---

## 1. Where we are today

### 1.1 Mobile in this repo

| Surface | Path | Stack | CI |
|---|---|---|---|
| Customer POS (web) | `apps/web` | React/Vite | `.github/workflows/ci.yml` job `web` |
| Customer POS (storefront) | `apps/storefront` | React | job `storefront` |
| Platform admin | `apps/admin` | React | job `admin` |
| API | `chmabapos_api` | FastAPI | job `api` |
| **Mobile** | **`apps/android`** | **Kotlin + Compose** | **job `android`** |
| Library surface | `packages/ui`, `packages/api-client` | React / TS | job `api-client` |

There is no `apps/ios`, and `grep`-ing the repo for `iOS` / `Xcode` / `App Store` /
`react-native` / `expo` / `flutter` returns nothing. This is a greenfield decision.

The **reference surface is `apps/web`** — `apps/android` documents itself as following
the web POS ("Its screens and visual language follow the web POS in `apps/web`", and
`DESIGN_GUIDE.md` claims "95%+ match to web design"). Any iOS work inherits that same
contract, which is a real advantage: the product decisions are already made.

### 1.2 What the Android app actually does

This is the parity baseline an iOS app would have to match. Measured, not estimated:

- **44 Kotlin source files, ~9,900 production lines.** `POSScreen.kt` alone is
  **1,987 lines**.
- **17 destinations read real API data**: Dashboard, Reports, POS, Orders (+detail),
  Products (+editor), Categories, Customers (+detail), Inventory, Suppliers,
  Purchasing, Plans, Settings, plus Login.
- **3 destinations are placeholders** — `Team`, `Activity`, `Help & support` render
  `PlaceholderScreen` with *"Not built in the Android app yet. Use the web POS for
  this screen."* (`MainShell.kt:377-384`).
- **~17 buttons are dead stubs** that only raise the `notYet(...)` notice
  (`MainShell.kt:103-108`). Full list in Appendix C.
- **71 hand-ported Lucide icons** (`ui/icons/ChmabaIcons.kt`, 231 lines) plus a
  4-colour `GoogleG` vector — all raw SVG path data.
- **17 unit tests** across 4 JVM test files; **0 instrumentation tests**.
- **Backend surface** is small and stable: 15 REST paths total (Appendix A).

Two things make the parity target *smaller* than it looks and worth stating plainly:

1. A meaningful slice of the Android app is **scaffolding and stubs**, not features.
   Porting the stubs would be wasted work.
2. The **hard, non-portable parts are narrow** — barcode scanning, OAuth deep links,
   session/cookie persistence, and back navigation. Everything else (DTOs, JWT skew
   maths, pricing, report periods, screen layout) is conventional.

See **Appendix A** for the per-destination matrix and **Appendix B** for the
Android-only surfaces.

---

## 2. The Windows constraint

Stated once, precisely, so we stop re-litigating it:

| Capability | Windows | Notes |
|---|---|---|
| iOS Simulator | **No** | macOS-only. No legitimate workaround exists. |
| Build / sign an `.ipa` | Via cloud Mac, **or** `xtool` in WSL | The cloud-Mac route is **free** for a public repo (§2.1). `xtool` still needs an ~8 GB `Xcode.xip` download from Apple to synthesise the Swift SDK. |
| Deploy to a physical iPhone | Via cloud Mac, or `xtool` + WSL USB passthrough | `usbmuxd` on Linux; WSL needs USBIPD, with a documented iTunes-relay fallback (`xtool` issue #19). |
| Interface Builder, SwiftUI previews, Instruments | **No** | `xtool` has no equivalent; it is CLI + SwiftPM only. |
| Upload to App Store Connect | **No** | `altool` / Transporter are macOS-only. Use a cloud Mac, or a service like EAS. |
| "macOS in a VM / Hackintosh" | **Don't** | Violates Apple's EULA and is operationally fragile. Not an option. |

**Consequence:** Windows can host the *editing* experience and, with `xtool`, a crude
device loop. It cannot host the *release* experience. Budget for macOS somewhere in
the pipeline regardless of which option below we pick.

### 2.1 macOS in CI is free for this repository

This is the fact that reorders the options below, so it is worth stating precisely.
From GitHub's own billing documentation:

> GitHub Actions usage is **free** for self-hosted runners and for **public
> repositories** that use standard GitHub-hosted runners.

`somvannda/chmabapos` is **public**, so `macos-latest` costs **$0** — not "cheap", and
not drawn from a monthly minute quota. By contrast, on a private repository macOS bills
at **$0.062/min** against **$0.006/min** for Linux, which is where the widely-quoted
"macOS is 10× more expensive" figure comes from. That premium is real, and it does not
apply to us.

Two caveats that the argument rests on:

- **Larger runners are always charged**, even for public repositories. Use
  `macos-latest`, not a `macos-*-large` variant.
- **If this repository ever goes private**, macOS minutes start costing money
  immediately. Re-check this section if visibility changes.

What that buys, concretely: a real iOS Simulator, SwiftUI previews, Instruments,
`xcodebuild` archiving, and App Store Connect upload — none of which `xtool` provides.

---

## 3. Options

### Option A — `xtool` (Swift / SwiftUI, SwiftPM, WSL)

A community "cross-platform Xcode replacement" (`github.com/xtool-org/xtool`, v1.2.x).
It builds a **SwiftPM package** into an iOS app, generates the cert + App ID +
provisioning profile via Apple Developer Services, signs, and installs to a device
over USB.

**What it gives us**

- A genuine device loop from Windows (WSL): `xtool new` → `xtool dev` builds, signs,
  installs, and launches on a connected iPhone.
- Apple Developer Services primitives as `ds` subcommands: teams, devices,
  identifiers, certificates, profiles.
- Two auth modes: **API key** (needs a paid membership, uses the public App Store
  Connect API — recommended) or **password** (any Apple ID, but uses *private* Apple
  APIs; the docs themselves suggest a throwaway Apple ID).
- IDE integration via Build Server Protocol (`bsp`) into VS Code + the Swift
  extension, so editing on Windows is reasonable.

**What it does not give us**

- **No simulator.** Device-only.
- **No distribution.** `Sources/XToolSupport/DSCommands/` has certificates, devices,
  identifiers, profiles, teams — and nothing for App Store / TestFlight. The final
  upload still needs a Mac.
- No Interface Builder, no asset-catalog tooling as Xcode does it, no previews, no
  Instruments.
- **SwiftPM only.** This is the decisive limitation: it rules out Kotlin Multiplatform
  (a KMP iOS target produces a framework that needs an Xcode project to bundle).
- Young project (v1.2.x) whose value partly depends on private Apple APIs. Tolerable
  for a throwaway experiment; poor footing for anything a store depends on.
- Free Apple ID ⇒ **7-day** provisioning profiles. Useless for a deployed store.

**Fit:** bad *foundation* — it means a third codebase in Swift, sharing nothing with the
Kotlin app. Its original reason to exist (avoiding the cost of a Mac) does not apply
here, because a macOS CI runner is already free (§2.1) — and `xtool` gives up the
simulator, previews, Instruments and distribution to get there. Even as a *spike* tool
it is now the slower path: the free macOS runner does the same job with a real
toolchain and no USB passthrough.

### Option B — Kotlin Multiplatform / Compose Multiplatform

Share the existing Kotlin investment: DTOs, the session/refresh machinery, JWT skew
logic, billing-cycle maths, report periods, and (with Compose Multiplatform) a large
part of the UI.

**What it gives us**

- Real reuse of a ~9,900-line codebase rather than a rewrite.
- One place to fix a business rule. Today `BillingCycleParityTest.kt` exists purely to
  keep Android in sync with `apps/web/src/features/marketing.jsx` — a third
  implementation would add a third thing to keep in sync, with no such test.
- The shared layer is genuinely tested already: 17 unit tests cover session refresh,
  cookie rotation, billing parity, and icon integrity.

**What it costs**

- **Requires macOS** for the iOS build (Kotlin/Native + Xcode toolchain). A cloud
  runner satisfies this and costs us **nothing** (§2.1). `xtool` cannot substitute.
- Compose Multiplatform on iOS is younger than Android Compose; the Android-specific
  bits (camera/zxing, `BackHandler`, intents, `SharedPreferences`) need iOS
  counterparts regardless — see Appendix B. These are the same four areas any option
  must solve.
- The iOS UI will need work to *feel* iOS-native, or we accept a shared-but-unified
  look. This is a product call, not a technical one.

### Option C — React Native / Expo + EAS Build

**What it gives us**

- **EAS Build and EAS Submit cover building *and* App Store submission with no macOS
  runner of any kind** — not ours, not a rented Mac, not a CI job. Cloud builds,
  TestFlight distribution, App Store Connect submission via API key.
- That advantage is narrower than it first appears, though: we never needed to *own* a
  Mac, because the public-repo macOS runner is free (§2.1). What EAS genuinely saves is
  the effort of writing iOS release automation — a convenience, not a cost
  breakthrough — and it is a paid service above its free tier.
- Reuses the TypeScript ecosystem and `packages/api-client`; the team already knows
  React from `apps/web`.

**What it costs**

- It shares **nothing** with the Kotlin app — so we'd end up with Kotlin Android +
  TS iOS, the worst parity-drift risk of any option.
- The alternative is converging *both* platforms onto React Native, i.e. rewriting
  the 9,900-line Android app. That's a much bigger project than "add iOS".
- No local simulator either; iteration is EAS + TestFlight, or Expo Go for JS-only
  changes.

**Fit:** only attractive if we intend to converge mobile onto one cross-platform
codebase. As a bolt-on iOS-only choice it creates a lasting two-stack problem.

### Option D — Cloud or rented Mac + native Swift/SwiftUI

The boring, complete option: GitHub Actions `macos-latest`, or a rented Mac
(MacStadium / MacinCloud / Scaleway Mac mini).

- Everything works: simulator, Instruments, previews, Interface Builder, archive, and
  App Store upload.
- Cost: **$0 for us.** This repository is public, so standard `macos-latest` runners
  are free (§2.1). The ~10× premium applies to private repos. A rented Mac (MacStadium /
  MacinCloud / Scaleway) is only needed if somebody wants an interactive Mac desktop.
- **It is a prerequisite for Option B**, and the backstop for Option A — which cannot
  perform the App Store upload at all.

**Fit:** an ingredient rather than an alternative to A/B/C — but a free one, which is
why it should be the default host for anything we spike or ship.

### Option E — No native iOS; web/PWA on iPad

The honest status quo: `apps/web` is a responsive POS, and iPads can use it in Safari
today.

**But it is not free.** We verified there is **no PWA manifest and no service worker**
in `apps/web` — no `manifest.json`, no `vite-plugin-pwa`, no Workbox. So today it is
"a website that happens to render on an iPad", with no install, no offline, no
full-screen, no camera-driven scanning story. `docs/offline-mode-plan.md` exists but
is a plan, not shipped behaviour. Choosing E means committing to PWA work, which is
its own project.

**Fit:** worth taking seriously if iOS demand is soft, and it is far cheaper than a
native client *if* the offline/PWA plan is something we want anyway.

---

## 4. Comparison

| | A. `xtool` | B. KMP / Compose MP | C. React Native + EAS | D. Cloud Mac + Swift | E. Web/PWA |
|---|---|---|---|---|---|
| Reuses the Kotlin app | **No** (Swift only) | **Yes**, most | No | No | N/A |
| Codebases after | 3 | 2 | 2 (or 1 if Android migrates) | 3 | 0 new |
| Dev loop on Windows | Device-only, in WSL | Common code yes; iOS build no | JS yes; native build no | Editing yes; build in CI | Full |
| Simulator / previews / Instruments | **No** | Yes | Yes | **Yes** | N/A |
| macOS runner required | No | Yes — **free** (§2.1) | No | Yes — **free** (§2.1) | No |
| Build `.ipa` without owning a Mac | Yes | Yes (free CI) | **Yes** (EAS) | Yes (free CI) | N/A |
| App Store submit without a Mac | **No** | Yes (free CI) | **Yes** (EAS Submit) | Yes (free CI) | N/A |
| Maturity / risk | Low maturity, private APIs | Mature-ish | Mature | Highest | Highest |
| Build effort | Third codebase from scratch | Reuses the Kotlin layer | Third codebase from scratch | Third codebase from scratch | PWA/offline project |
| Recurring cost | $99/yr | $99/yr | $99/yr + EAS plan | $99/yr | $99/yr (n/a for web) |

---

## 5. Recommended sequence

**Stage 0 — Decide whether iOS is required.** Ask the actual question: are any stores
asking for it, and is the cashier device ever an iPad? Android dominates cheap POS
hardware and is where scanning/peripherals work best. If nobody is asking, the correct
answer is Option E or nothing, and this doc is done.

**Stage 1 — Prove the loop on the free macOS runner (only if Stage 0 says "maybe").**
~1 week, one developer. Add a `macos-latest` job that builds a trivial SwiftUI app and
gets it onto a device via TestFlight, then extend it to the *smallest honest slice*:
Login → product grid → cart → cash checkout, hitting the real API. Do not port stubs.
Output is a go/no-go on both demand and the toolchain. Discard the code.

Do **not** do this with `xtool` unless a developer specifically wants a Windows-only
loop. It is slower, needs a USB-passthrough dance with a documented failure mode, and
still cannot do the App Store upload that the free runner already handles.

**Stage 2 — If go, choose the destination.** Option B if we value the Kotlin
investment; Option C only if we intend to converge both platforms onto one stack.
Either way the CI host is the same free `macos-latest` runner, so this decision is
about code and people, not cost.

**Stage 3 — Release plumbing.** Signing, TestFlight, an App Store Connect API key, and
an `ios` CI job. Free at our scale, but it is real work and should be scheduled rather
than discovered.

---

## 6. Effort estimate

Anchored to the measured Android app rather than guessed. Shape, not schedule;
assumes one experienced developer and that the same person knows the Android code.

| Work | Size driver |
|---|---|
| Non-portable platform layer (auth deep links, session/cookie persistence, token refresh, back navigation, camera scanning) | Small in lines, **highest risk**; Appendix B |
| Design system + icons | 71 Lucide icons, colour/type/spacing scale already specified in `DESIGN_GUIDE.md`; reusable as spec, not as code |
| POS screen | `POSScreen.kt` is 1,987 lines — the single largest item by far |
| Second tier (Dashboard, Products, Customers, Orders) | 695 + 637 + 517 + 480 lines on Android |
| Remaining destinations (Reports, Inventory, Purchasing, Suppliers, Categories, Plans, Settings, auth, splash) | The long tail; mostly list + filter + badge screens |
| **Skip** | The 3 placeholders and ~17 `notYet` stubs (Appendix C) |
| Release plumbing | macOS runner, signing, TestFlight, App Store review |

Rules of thumb that hold across all options: the POS screen is ~20% of the Android
app's lines and will be a similar share of the port; the ~15 endpoints are trivial;
the platform layer is where schedule surprises live.

---

## 7. Prerequisites and open questions

**Prerequisites**

- Apple Developer Program membership, **$99/year** (organisation enrolment takes
  longer than personal and needs a D-U-N-S number — start early).
- A physical iPhone or iPad for hands-on testing. There is no simulator on Windows, and
  a CI runner's simulator is headless — fine for automated tests, useless for poking at
  the UI — so a real device is still needed for interactive work.
- A macOS runner for anything shipped — and this is **already free**: standard
  `macos-latest` runners cost nothing on public repositories (§2.1). No purchase, no
  rented Mac, no monthly minute quota to manage.
- A decision on whether the iOS app should look platform-native or match the
  Android/web design system.

**Open questions**

- Which stores/users actually need iOS? Is the iPad a cashier device for us, or a
  manager/back-office device?
- Do we want the iOS UI to be visually identical to Android (`DESIGN_GUIDE.md`) or
  native iOS?
- Do we want to fix the stubs (KHQR confirmation, receipts, modifiers) on **both**
  platforms, or only where the demand is? See Appendix C — several are
  customer-visible gaps, not just "not built".
- If Option E is on the table, do we want the PWA/offline work
  (`docs/offline-mode-plan.md`) regardless of iOS?
- Do we need app-store presence at all, or is an enterprise/TestFlight distribution
  to specific stores enough? This materially changes the release path.

---

## Appendix A — Android feature/UI parity matrix

Destinations the shell can reach, what they do, and what backs them.

**Shell structure** (`MainShell.kt`): bottom tabs `Home / POS / Orders / More`; a
`ModalNavigationDrawer` grouped **Selling** (Products, Customers, Categories),
**Stock** (Inventory, Purchasing, Suppliers), **Business** (Reports, Team, Activity),
**Account** (Billing & plans, Settings, Help & support), with Sign out pinned.
Navigation is hand-rolled `mutableStateOf` — **no Navigation library and no DI
framework**; ViewModels are default-constructed per screen.

| Destination | Android source | Endpoints | Capabilities | iOS port cost driver |
|---|---|---|---|---|
| POS | `pos/POSScreen.kt` (1987), `pos/PosViewModel.kt` (170) | `GET products?active_only=true`, `GET modifier-groups`, `POST orders` | Grid + search + category chips; cart with stock caps; single-select modifiers; percent/flat discount; customer attach; in-memory held orders; Cash (with change) and KHQR; scan | **Largest single item.** Bottom-sheet-heavy mobile layout, 7 sheets |
| Dashboard | `dashboard/DashboardScreen.kt` (695) | `GET reports/summary` | 4 metric cards, period switch, daily bar chart, top products, recent transactions, quick actions | Custom charts (`Canvas`) |
| Orders + detail | `orders/OrdersScreen.kt` (480), `OrdersViewModel.kt` (175) | `GET orders?limit=50`, `GET orders/{id}` | Filter chips All/Paid/Pending/Pickup/Cancelled; status/tender badges; detail with totals, amount paid, change | Straightforward list/detail |
| Products + editor | `products/ProductsScreen.kt` (637) | `GET products`, `POST products`, `PATCH products/{id}` | Search, category filter, stat row; full editor: price/cost/tax/barcode/brand/category/description/reorder point, track-inventory and track-serials toggles | Largest form; category matched **by name** |
| Categories | `categories/CategoriesScreen.kt` (217) | `GET categories` | Parent/child tree, active badges, stat row | Simple |
| Customers + detail | `customers/CustomersScreen.kt` (517), `CustomersViewModel.kt` (154) | `GET customers?search=`, `GET customers/{id}` | Search by name/phone; detail with orders/spent/points and a points stepper + quick chips | Loyalty stepper logic |
| Inventory | `inventory/InventoryScreen.kt` (434) | `GET inventory?low_stock=`, `PATCH inventory/{productId}` | All/Low/Healthy filters; stock value + units stats; adjust-stock dialog (absolute on-hand); serials card | Real write path |
| Purchasing | `purchasing/PurchasingScreen.kt` (320) | `GET purchases?limit=50` | Status filter chips, stat row, PO rows | Read-only today |
| Suppliers | `suppliers/SuppliersScreen.kt` (180) | `GET suppliers` | Search, active badges | Simple |
| Reports | `reports/ReportsScreen.kt` (419) | `GET reports/summary` | 5 period presets, 4 metric cards, sales-by-day chart, payment breakdown, top categories | Charts again |
| Billing & plans | `plans/PlansScreen.kt` (442), `Plans.kt` (plans VM + price maths) | `GET plans` (public) | Monthly / semi-annual (−15%) / annual (−20%) selector, plan cards, marketing bullets, "most popular" | Price maths already unit-tested |
| Settings | `settings/SettingsScreen.kt` (289) | none | Static rows; **non-persisted** feature-pack switches; display-only hardware rows; real Sign out | Mostly a config surface — decide what's real |
| Login | `auth/AuthScreens.kt` (394), `LoginViewModel.kt` (94) | `POST auth/login`, `GET workspaces/current`, `GET auth/me`, `POST auth/refresh` | Email/password, remember-me, Google sign-in | Session/cookie machinery |
| Signup / Verify / Reset | `auth/AuthScreens.kt`, `AuthComponents.kt` (378) | **none** | UI only — no backend calls | Rebuild properly, don't port |
| Splash | `splash/SplashScreen.kt` (240) | none | 3 fixed 1500 ms stages, timer-driven | Cosmetic |

**Shared UI** (`ui/components`, 7 files): `ChmabaButton` (6 variants × 3 sizes),
`ChmabaCard` / `ProductCard` / `StatCard`, `ChmabaTextField` / `ChmabaSearchBar`,
`ChmabaBadge` (6 tones) + `StatusBadge` (6 order statuses), `ChmabaBottomNav`,
`ChmabaLogo`, `LoadStateNotice`, `BarcodeScanner`.

**Design system** (`DESIGN_GUIDE.md`, 334 lines) — reusable as a **spec** for iOS:
purple `#6957F5`, lime `#C4F27C`, a 9-step grey ramp, 4 accents, a 6-step type scale,
button/card/badge/field metrics (button 40 dp, radius 12; product card 140×180; badge
radius 6), a 4→48 dp spacing scale, dark-mode palette (`#111114` / `#1A1B20` /
`#E4E4E8`), 300/150/200/250 ms transitions, and grid breakpoints (2 cols phone, 3–4
tablet, 4–5 large).

**Auth/session architecture** (worth reimplementing deliberately, not transliterating):
60-minute access token; refresh cookie issued at login and **rotated by the server**
(so refresh is serialised behind a `Mutex` on Android); renewal when within 120 s of
expiry, capped at lifetime/3; a custom persistent cookie jar keyed per host; JWT
`exp` parsed by hand.

---

## Appendix B — Non-portable Android surfaces

Where the genuine iOS engineering is — everything else is ordinary porting. The first
four rows are the real risk (scanning, OAuth, persistence, back navigation); the rest
are small but easy to overlook.

| Android | Where | iOS counterpart |
|---|---|---|
| zxing `ScanContract` — delegates to the **system camera app** | `ui/components/BarcodeScanner.kt`; used at `POSScreen.kt:1611` | `AVCaptureSession` + `VNDetectBarcodesRequest`. iOS has **no** "launch the system scanner" contract — this must be built |
| `Intent(ACTION_VIEW)` to the system browser for OAuth | `data/auth/GoogleAuth.kt:39-41` | `ASWebAuthenticationSession` |
| `chmaba://auth` deep link via `onNewIntent` + `Uri` fragment parsing | `GoogleAuth.kt:44-60`, `MainActivity.kt:27,40-55`, `AndroidManifest.xml:32-37` | Custom URL scheme / Universal Links via `onOpenURL`; `CFBundleURLTypes` in `Info.plist` |
| `SharedPreferences` for token + profile + refresh cookies | `data/auth/SessionPersistence.kt` | **Keychain** (prefer over `UserDefaults` for the token) |
| okhttp custom `CookieJar` | `data/auth/SessionRefresh.kt:23-76` | `URLSession` + `HTTPCookieStorage` |
| `BackHandler` with bespoke nested unwind (`tab` → `moreDest` → `openOrder` → `openCustomer` → `editingProduct`) | `MainShell.kt:147-154`, `AppRoot.kt:68-75` | `NavigationStack` / `UINavigationController` — the unwind logic is bespoke and must be redesigned |
| `usesCleartextTraffic` for `http://localhost:5173` | `AndroidManifest.xml:10-14`, `ApiClient.BASE_URL` in `data/plans/Plans.kt:111` | ATS exception for dev only |
| Status-bar colour/insets via `WindowCompat` / Activity window | `ui/theme/Theme.kt:3,56-62` | SwiftUI scene / `preferredStatusBarStyle` |
| `material-icons-extended` fallback icons | `ui/components/ChmabaTextField.kt` | SF Symbols, or reuse the ported Lucide paths |

**Dev-environment gotcha to carry over:** the app deliberately targets
`http://localhost:5173/api/v1/` — the **Vite dev-server origin**, not the API port —
because the OAuth CSRF cookie and Google's callback must share a host, and
`GOOGLE_REDIRECT_URI` is registered against `localhost`. Android reaches it via
`adb reverse tcp:5173 tcp:5173`. **`localhost` is load-bearing.**

That constraint then splits by route, and this is a real argument for the simulator:

- **On a simulator** (a macOS runner, or a Mac) it is satisfied for free. The iOS
  Simulator shares the host's network stack, so `localhost:5173` inside the simulator
  *is* the host's `localhost:5173`. Run the Vite dev server alongside the build on the
  same machine and Google sign-in works unchanged.
- **On a physical device** it is not. The phone's `localhost` is the phone, and iOS has
  no `adb reverse` equivalent — `iproxy` forwards the wrong way (host → device). You
  must point the app at the PC's LAN IP instead, which needs an ATS cleartext exception
  **and breaks Google sign-in**, because the redirect URI is registered against
  `localhost`. Email/password only.

**Portable almost 1:1** (no redesign needed): the DTO shapes, JWT skew logic, the
billing-cycle price maths, report period presets, and the screen layouts
conceptually.

---

## Appendix C — Do not port the stubs

Three classes of not-built-yet surface exist. Porting them would be pure waste.

**1. Placeholder destinations** (`PlaceholderScreen`, `MainShell.kt:377-384`):
`Team`, `Activity`, `Help & support`.

**2. Dead buttons** — each raises `notYet(...)` (`MainShell.kt:103-108`):
printing a receipt (242), refunding an order (243), cancelling an order (244), adding a
customer (257), editing a customer (270), opening an order from here (271), adding a
category (276), renaming a category (277), receiving stock (281), exporting inventory
(282), exporting a report (355), opening a purchase order (359), creating a purchase
order (360), creating orders from suggestions (361), opening a supplier (365), adding a
supplier (366), opening a settings section (371).

**3. Partly-built or simulated** — these *look* finished and are not:

- Signup, email verification and password reset are **UI only; no API calls**
  (`AppRoot.kt:96-115`). "Confirm email & continue" drops straight into the app.
- **KHQR payment is a static QR glyph** with no payload, no polling and no
  confirmation (`POSScreen.kt:1776-1808`) — tapping Complete immediately posts the
  sale as `khqr`. This is a real correctness gap, not a UI gap.
- **Scanning resolves against a hard-coded demo product list**, not the loaded
  catalogue (`POSScreen.kt:435-438`), so only the 8 demo SKUs match.
- Customer "Add points" button is a no-op (`CustomersScreen.kt:378-383`); the Orders
  refresh icon is a no-op (`OrdersScreen.kt:135`).
- Settings feature-pack switches are local `remember` only, never persisted
  (`SettingsScreen.kt:71-73`).
- Product image upload and "Variants → Add" are static affordances
  (`ProductsScreen.kt:481-508, 522-541`).
- Splash timing is fixed at 3 × 1500 ms and not tied to the real session check
  (`SplashScreen.kt:73-80`).
- Multi-select modifier groups are unsupported — one option per group, only
  `is_required` honoured (`README.md`).
- Editing a product's reorder point is impossible: `ProductUpdateRequest` has no such
  field.

**Recommendation:** fix KHQR confirmation, real receipt printing and real scan-to-SKU
**once, in the API or shared layer**, before or alongside any iOS work. Otherwise iOS
inherits the gaps and we pay for them twice.

---

## Appendix D — Stale documentation found while writing this

`apps/android/README.md` was out of date in ways that affected planning. **All three
items below were corrected in #666**, so the README no longer makes these claims; the
table is kept as a record of what the audit found.

| Stale README claim | Reality |
|---|---|
| "There is no Unix `gradlew` committed, only `gradlew.bat`" | `apps/android/gradlew` exists (8,963 bytes) |
| "`.github/workflows/ci.yml` has no `android` job yet" | Job `android` exists at `ci.yml:258-277` (ubuntu-latest, JDK 17, `assembleDebug` + `testDebugUnitTest`) |
| "`testDebugUnitTest` currently runs 12 tests" | 17 tests across 4 files |

**Still outstanding:** `AGENTS.md` describes the merge gate as "API, Web, Admin", but
`ci.yml` actually gates on `api`, `web`, `storefront`, `admin`, `e2e`, `api-client`,
`ops-config`, `front-image` and `android`. That file is the repository's working
agreement for every contributor, so it is worth correcting deliberately rather than
incidentally.

Note also that the "Known gaps" section of `apps/android/README.md` was rewritten in
#666, replacing a stale CI entry with gaps that still exist — and those gaps are
tracked in issue #670.
