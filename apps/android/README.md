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
printing, cash-drawer pulses, USB peripherals, shift management. Scanning is the only
hardware integration. Offline trading is not among them either: the queue holds a sale
the network could not carry, but the catalogue itself still has to come from the server.

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

The emulator itself needs one non-default flag. `Pixel_9` is a 16 KB page-size image, and with the
host GPU its window comes up **black** on this machine while the device underneath renders fine —
the app, the tunnel and the API are all unaffected; only the window is. Pin the renderer rather than
leaving it to `-gpu auto`:

```bash
emulator -avd Pixel_9 -gpu swiftshader_indirect
```

Two symptoms of getting this wrong, both worth recognising: a black window, and `uiautomator dump`
returning the launcher instead of the app (the AVD also exposes a secondary display, and a
`SecondaryDisplayLauncher` competes for the top). If a dump shows the launcher while `pidof
com.chmaba.pos` still answers, the app is fine and the window is the problem.

## Build and test

```powershell
# Windows
.\gradlew.bat assembleDebug
.\gradlew.bat testDebugUnitTest
.\gradlew.bat installDebug
```

Both wrappers are committed, and `.github/workflows/ci.yml` has an `android` job
(`ubuntu-latest`, JDK 17) that runs `assembleDebug` and `testDebugUnitTest`.

`testDebugUnitTest` runs everything in `app/src/test`: icon parity with Lucide,
billing-cycle parity between the app and the plan table, JWT expiry and clock
skew, refresh-cookie rotation and the cookie jar's persistence, `money()` and the
sign an input may carry against the store's currency, which serials a product may
offer a till, how an API error is worded, the body a sale is posted with, the price
the editor inherits from the catalogue, how an audit instant is rendered in the
reader's own zone, and the payload shapes behind Team and Help.

None of them touch the network, which is how a request body the API refuses
reached `main` with every check green — see *Nothing in CI exercises a real
request* under Known gaps.

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
Categories, Customers (+ detail), Inventory, Suppliers, Purchasing, Plans,
Settings, Team, Activity and Help. List screens show loading, failure (with the
API's message) and a retry.

Team, Activity and Help were the last three placeholders, and each now reads the
API while saying what it does *not* do:

- **Team** lists the company's members, their roles and the stores they reach
  (`GET /team`). There is no invite form: `POST /team/invitations` is real and
  unwired, so the screen has no control for it.
- **Activity** lists what the team changed (`GET /audit-logs`), newest first, with
  each entry's action, actor, entity type and its own details.
- **Help** shows the guides (`GET /support/articles`), already filtered by the
  company's vertical and the member's role. The AI assistant is not here:
  `POST /support/chat` and the ticket endpoints are real and unwired, and the More
  row says "Guides" rather than promising a conversation.

Where the API has no equivalent for something the UI mock-up invented, the
figure was removed rather than faked — inventory stock value is only shown for
rows that have a recorded cost, suppliers show no payment terms (the payload has
none), and there are no per-category product counts (the payload has none).

Three affordances that only raised a notice are now real. The scan sheet resolves a
code against the loaded catalogue by SKU, barcode or name; Inventory's Export fetches
the API's own `products/export.csv`; and Reports' Export fetches `reports/gdt-csv`. Both
exports hand the file to the system share sheet.

## Known gaps

- **KHQR cannot be completed in this app.** The tender shows no payable code and polls
  nothing, so the app refuses to complete a KHQR sale rather than record a payment that
  cannot have happened. Taking KHQR needs the payment provider wired in.
- **Printing a receipt needs hardware** the app does not talk to, so the button
  raises a notice.
- **Settings: store details, the tax rate and the currency are real, the rest are notices.** That
  screen edits the store's name, address, phone, email, service tax rate and currency through
  `PATCH /stores/{id}` — the same endpoint and fields the web POS uses — and the till takes both a
  saved rate and a saved currency at once, without a restart. The currency picker offers what
  `GET /settings/currencies` has enabled for this company rather than a list kept here — not the
  platform's whole catalogue, which a save would refuse — and the screen says what a currency change
  means: prices are bare numbers, so it renames the amounts rather than converting them. The other
  rows stay notices, but for a different reason than this list used to give: the API is not missing
  the endpoints. The same request also takes the receipt preferences, and a payment link has its own;
  those are not offered because each needs a decision (what a receipt says, which provider to point
  at) rather than a setting. Reports' Export is real but plan-gated — `reports/gdt-csv` needs
  `advanced_reports`, so a free workspace is refused, and the screen says so before the reader tries.
- **Editing a product's reorder point is not possible**: `ProductUpdateRequest`
  has no `reorder_point`, only `ProductCreateRequest` does.
- **A purchase order carries lines, a supplier, a unit cost and a receiving step.** New PO collects a
  basket - the same product twice adds to its quantity rather than repeating the line - and a
  supplier from the store's own list, or none, as the server allows. Each line can also take a unit
  cost, which is optional because the API takes none: it is stored with the line and read back when
  the order is received, where it becomes the cost basis of what arrives. An ordered order can be
  received from its row, which is what moves the stock: it is confirmed first, because nothing here
  can put stock back, and the server's own refusal is shown as it comes - a serial-tracked product
  has to be received from Stock so each unit gets a serial. A product sold in variants is refused by
  the server with a message naming it, and that message is shown as it comes rather than pre-empted.
  A raised order can also be cancelled from its row, which moves no stock and marks it Cancelled; the
  server also allows deleting one that was never received, which this app does not offer, and neither
  action offers a way back.
- **Inventory shows a product's variants, and Adjust can change one.** Each row lists its variants
  with their own on-hand and a reorder hint, because a product sold in variants carries its own
  balance *and* one per variant, and showing only the first was worse than showing nothing - the
  figure looked like it meant something. A variant's line opens the dialog for that variant, which
  names it and starts from its balance, and the request carries the variant id
  (`InventoryAdjustBody.variantId`); without it the API writes the product's own balance, a number no
  sale draws on.
- **Inventory's Receive is not the web's.** The web receives into a chosen product *and variant*, and
  its request carries a supplier, a reference, a unit cost and, for a serial-tracked product, one
  serial per unit - refusing until a variant is chosen when the product has any. This app offers one
  toolbar button that acts on the first row of whatever filter is showing, and sends a bare positive
  delta with no variant (`InventoryRestockBody`), so stock received here is unattributed and cannot be
  aimed at the product the cashier is looking at. Adjust no longer needs that button, because a row is
  the way in; correcting Receive is a form rather than a sentence.
- The reorder-suggestions card on Purchasing is hidden until something can
  supply it; no endpoint does today.
- Product category is matched by name against the store's categories; a typed name
  that matches nothing blocks Save rather than silently dropping the category.
- **Plan-gated actions are only reachable as refusals on a free plan**: supplier
  creation, purchase orders and refunds are gated server-side, so their success
  paths need a paid workspace.
- **CI exercises exactly one real request.** The `android` job builds and runs the unit
  tests above, none of which touch the network, and the `api` job posts a sale of its own to
  the real endpoint — `chmabapos_api/tests/test_android_sale_contract.py`. What it posts is
  the till's own body: `SaleBodyContractTest` pins `saleBody()` to
  `app/src/test/resources/android-sale-body.json`, and that file is what the API test sends.
  So a body the API refuses can no longer ship green, which is how the till came to send
  `payment_method` and `tenders` together — a pairing `POST /orders` refuses (v1.py:5604) —
  and so fail every sale, from its first commit until it was caught by hand. Sales, purchase orders
  and refunds are covered; nothing else this app sends is.
- **The offline queue goes when the network says so.** A sale the till could not send is held and
  replayed: the body that failed is kept with the `client_order_id` it was minted with, so a replay
  is the same sale rather than a second one, and what may be queued is a rule with a test — a request
  that never reached the server is kept, while one the server *answered* (400, 403, 422) was refused
  for a reason. The flush runs when the app opens, when the till opens, and now **when the connection
  comes back**, which is the one that needs nobody to act. The till says what it is holding, and
  names the reason when the server has refused one, because a refused sale will never send itself and
  a cashier who believes it has gone is the worst case of all. Nothing is ever dropped, so no sale is
  lost. One wrinkle: an error sheet that was open when an automatic flush sent the sale behind it still
  says the sale is waiting. Dismissing it is harmless — "Try again" re-submits the same
  `client_order_id`, and the API answers with the order it already made, so nothing is recorded twice —
  and the sale itself has gone.
