# Chmaba Cloud POS — native Android app

An Android client for Chmaba Cloud POS, written in Kotlin with Jetpack Compose.
Its screens and visual language follow the web POS in `apps/web`.

## What is actually here

- **Kotlin + Jetpack Compose**, Material 3, minSdk 24, compileSdk 34.
- **MVVM without Hilt.** Each screen default-constructs its view model through
  `androidx.lifecycle.viewmodel.compose.viewModel()`. There is no DI framework.
- **Retrofit + OkHttp + Gson.** One shared `OkHttpClient` (`data/plans/Plans.kt`,
  `ApiClient.http`) carries the cookie jar and the session interceptor; every
  repository builds its Retrofit from it.
- **SharedPreferences for persistence** (`data/auth/SessionPersistence.kt`), not
  Room. Only the access token, a small profile and the refresh cookies are kept.
- **Scanning** uses `com.journeyapps:zxing-android-embedded`. CameraX and ML Kit
  were removed because the test emulator is a 16 KB page-size image and their
  native libraries tripped the compatibility dialog; **the APK ships no native
  libraries at all**.

Not present, despite what this file used to claim: Hilt, Room, NFC, Bluetooth
printing, cash-drawer pulses, USB peripherals, offline sync, shift management.
Scanning is the only hardware integration.

## Getting the app talking to an API

The app calls `http://localhost:5173/api/v1/` — the **Vite dev-server origin** —
not the API port directly.

That indirection is required for Google sign-in: the OAuth `state` lives in a
CSRF cookie, so the authorize request and Google's callback must be served by the
same host. `GOOGLE_REDIRECT_URI` is registered as
`http://localhost:5173/api/v1/auth/google/callback`, and cookies are per-host, so
`localhost` (not `127.0.0.1`) is load-bearing.

```bash
# 1. API (port 8000 is taken by an unrelated ChmabaPay service)
uvicorn app.main:app --app-dir chmabapos_api --port 8001

# 2. Web dev server, bound to IPv4 so `adb reverse` works
cd apps/web && npm run dev -- --host 127.0.0.1

# 3. Tunnel the emulator's localhost to the host — re-run after every emulator
#    restart, or the app gets an empty response
adb reverse tcp:5173 tcp:5173
```

## Build and test

```powershell
# Windows
.\gradlew.bat assembleDebug
.\gradlew.bat testDebugUnitTest
.\gradlew.bat installDebug
```

Both wrappers are committed, and `.github/workflows/ci.yml` has an `android` job
(`ubuntu-latest`, JDK 17) that runs `assembleDebug` and `testDebugUnitTest`.

`testDebugUnitTest` currently runs 17 tests across four files (icon parity,
billing-cycle parity, JWT expiry/skew, and refresh-cookie rotation).

## Layout

```
app/src/main/java/com/chmaba/pos/
├── MainActivity.kt                  # restores the session, restores the cookie jar
├── data/
│   ├── auth/                        # Session, SessionStore, SessionRefresh, Google deep link
│   ├── catalog/                     # products, categories, modifier groups, product writes
│   ├── orders/                      # Session holder, order creation
│   ├── plans/                       # ApiClient (base URL + shared client), plans
│   ├── reports/                     # GET /reports/summary
│   └── store/                       # orders, customers, inventory, suppliers, purchases
└── ui/
    ├── components/                  # buttons, cards, fields, badges, nav, LoadStateNotice
    ├── icons/                       # Lucide-parity icon set
    ├── screens/                     # one package per screen, shell/ is the drawer + tabs
    └── theme/                       # colour, type, theme
```

## Sessions

- Sign-in stores the access token and profile in SharedPreferences, so a killed
  app returns to the dashboard.
- Google sign-in extends the backend flow: `platform=android` on
  `/auth/google/authorize` sets a cookie, and the callback redirects to the fixed
  `chmaba://auth` target.
- Email sign-up is wired end to end: `POST /auth/register` creates the account and
  `POST /auth/verify-email` confirms the emailed code, which is what makes sign-in work.
  The "Remember me" box is sent as `remember_me`, and the API answers it with a 30-day
  refresh cookie instead of an 8-hour one.
- Password reset only makes the request (`POST /auth/request-password-reset`). The API
  emails a link carrying the token, and that link opens the web app, where the reset is
  finished - this app has no screen that can consume a token.
- The access token expires after **60 minutes**. `SessionRefresh` renews it from
  the httpOnly `chmaba_refresh` cookie a little before it lapses, serialised by a
  mutex because the server rotates the cookie and a repeated rotation is
  rejected.
- **The refresh cookie is only issued on login**, so after installing this build
  you must sign out and sign in once for renewal to work. Until then the app
  still fails an hour in.

## Screens reading the real API

Dashboard, Reports, POS, Orders (+ detail), Products (+ editor, create and edit),
Categories, Customers (+ detail), Inventory, Suppliers, Purchasing, Plans and
Settings. List screens show loading, failure (with the API's message) and a
retry.

Where the API has no equivalent for something the UI mock-up invented, the
figure was removed rather than faked — inventory stock value is only shown for
rows that have a recorded cost, suppliers show no payment terms (the payload has
none), and there are no per-category product counts (the payload has none).

Two affordances that only raised a notice are now real. The scan sheet resolves a
code against the loaded catalogue by SKU, barcode or name, and Inventory's Export
fetches the API's own `products/export.csv` and hands it to the system share sheet.

## Known gaps

- **Product image upload is static**: the picker is not wired.
- **KHQR cannot be completed in this app.** The tender shows no payable code and polls
  nothing, so the app refuses to complete a KHQR sale rather than record a payment that
  cannot have happened. Taking KHQR needs the payment provider wired in.
- **Printing a receipt needs hardware** the app does not talk to, so the button
  raises a notice.
- **Report export and the Settings sub-screens are notices**: the API exposes
  `products/export.csv`, which Inventory's Export fetches and shares, but there is
  no report export and no endpoint behind store details, tax, payments or receipts.
- **Multi-select modifier groups** are unsupported: the ring-in sheet picks one
  option per group, so only `is_required` is honoured.
- **Editing a product's reorder point is not possible**: `ProductUpdateRequest`
  has no `reorder_point`, only `ProductCreateRequest` does.
- The reorder-suggestions card on Purchasing is hidden until something can
  supply it; no endpoint does today.
- Product category is matched by name against the store's categories; a typed name
  that matches nothing blocks Save rather than silently dropping the category.
- **Plan-gated actions are only reachable as refusals on a free plan**: supplier
  creation, purchase orders and refunds are gated server-side, so their success
  paths need a paid workspace.
