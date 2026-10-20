# Currency policy: pricing vs accepting

Status: Proposed — design only. No code changes in this document's PR.
Owners: Engineering / Product
Scope: what "enabling KHR" means for a workspace, the full set of payment-tender
combinations, the rules that keep mixed-currency money correct (rate snapshots,
change, refunds, deposits, shifts), and the rollout that keeps USD-only merchants
unchanged.

Related: `docs/product-model.md`, `docs/billing-model.md`,
`docs/chamabapay-migration-plan.md`, `docs/marketplace-storefront-plan.md` §13.1,
`chmabapos_api/app/models.py` (`Currency`, `ExchangeRate`, `Payment`),
`apps/web/src/features/sales.jsx` (POS tenders).

---

## 1. The two concepts, kept separate

These are often conflated. They are different decisions with different gates.

| | **Pricing currency** | **Accepted (tender) currencies** |
|---|---|---|
| Question it answers | "What is this item's price?" | "What money may the customer hand over?" |
| Cardinality | **Exactly one per store** | Up to two (see §3) |
| Stored on | `Store.currency_code` (company `primary_code` is the default) | `CompanyCurrency` rows + `ExchangeRate` |
| Gate | The currency must be **enabled** for the company (verified: setting `currency_code="KHR"` when KHR is not enabled answers `400 "Currency KHR is not enabled for this company"`) | `multi_currency` plan feature when more than one is enabled |
| Changes a product? | No — one price list, one price field | No — conversion happens at payment, never at pricing |

**Consequence, and the point of this document: the seller never prices a product
twice.** A $3.00 latte is $3.00. If the business accepts riel, the *tender* is
converted at the rate in force for that sale; the product has one price.

## 2. What "enabling KHR" does and does not do

Enabling KHR as a company currency means **"this business may price or quote in
riel"**. It does **not** mean the business can take riel money.

Taking riel money needs a second, independent thing: a **KHR ABA PayWay link**
(Settings → Bank & KHQR, stored per currency — see `docs/marketplace-storefront-plan.md`
§13.1 and the per-currency map `aba_payway_links`).

This separation is deliberate:

- Quoting in riel and taking only dollars is normal in Cambodia (dual-currency
  price tags, cash at the counter).
- Auto-enabling riel *payments* when riel is enabled would either fail at the
  provider (`currency_not_configured`) or — far worse — fall back to the USD link
  and take dollars for a riel price. The public-order path now refuses that with a
  message naming the currency.

**Rule:** enabling a currency turns on pricing/display. Payments per currency are
turned on by that currency's verified link.

## 3. Decision: two currencies, not many

**Adopt USD + KHR only (a base plus one alternate).** Reasons:

1. Every extra currency multiplies the tender/change/refund matrix and the rate
   table, for a market that uses two.
2. Reports and drawer counts stay legible: base totals plus one alternate.
3. The provider already models a store as holding **one link per currency, at most
   one USD and one KHR** — the payment rail itself is dual.

**Gap found in the current code:** `CurrencySettingsRequest.enabled_codes` allows
up to **20** entries. Dual-only must be enforced **server-side** (cap at 2), not
just hidden in the UI.

## 4. The full tender matrix

A sale is one or more **tenders**. Each tender = a **method** (cash | KHQR) × a
**currency** (USD | KHR), with an amount.

### 4.1 Single tender (the common case)

| # | Tender |
|---|---|
| 1 | Cash USD |
| 2 | Cash KHR |
| 3 | KHQR USD |
| 4 | KHQR KHR |

A **pure-KHR store** (§7) uses 2 and 4; a USD-only store uses 1 and 3.

### 4.2 Two tenders

| # | Composition | Allowed? |
|---|---|---|
| 5 | Cash USD + Cash KHR | ✅ |
| 6 | Cash USD + KHQR USD | ✅ |
| 7 | Cash USD + KHQR KHR | ✅ |
| 8 | Cash KHR + KHQR USD | ✅ |
| 9 | Cash KHR + KHQR KHR | ✅ (the pure-KHR store's mixed case) |
| 10 | KHQR USD + KHQR KHR | ❌ **already refused** — the POS rejects more than one KHQR tender (`khqrCount > 1`), and the QR must cover the remaining balance |

Two QR codes would mean two concurrent payment intents for one bill; no provider
settles that cleanly, and it doubles the reconciliation surface. One QR per sale.

### 4.3 Three or more tenders

Legal only as **cash + cash + one QR** (e.g. Cash USD + Cash KHR + KHQR USD). The
QR is still the remainder and still unique. If we cap tender lines for simplicity,
cap at **three lines**, never at two QR lines.

### 4.4 Axes that are not tender combinations but change the maths

| Axis | Rule |
|---|---|
| **Change** | Given in **one** currency, chosen by the cashier, at the sale's rate. KHR change rounds to whole riel (§6). |
| **Refund** | Mirrors the tender composition, proportionally, in the same currencies (§6.4). |
| **Deposit / balance** | Two intents, two rate snapshots, possibly two currencies. |
| **Trade-in / loyalty credit** | Always computed in base, applied **before** tenders. |
| **Over/under tender** | Over-tender creates change; under-tender is refused. |
| **Tips / tax** | Computed in base, converted once per tender — never rounded twice. |

## 5. Data rules

1. **One base per store.** Every report, Z-report and ledger total is expressed in
   the store's `currency_code`. Alternate-currency figures are informative only.
2. **Snapshot the rate on the payment.** `Payment.exchange_rate` already exists;
   the sale must be read from its own snapshot, never from today's rate table.
3. **Store both amounts.** Each tender keeps `amount` (in its currency) and the
   base amount; conversion must not be re-derived later.
4. **Never re-price a product** to accept another currency.
5. **KHR has no subunit.** Amounts, tax, tips and change round to whole riel.
6. **Rate provenance.** The rate a sale used is part of the sale. A later rate
   change must not restate history.

## 6. Edge cases that break mixed-currency systems

### 6.1 Switching a store's currency after sales exist
Old orders keep their own `currency_code`. Reports group by the order's currency
and use its snapshot; history is never re-converted. The company `primary_code`
change is a display default, not a rewrite.

### 6.2 Rounding
KHR has no subunit, so tax and change round. Pick **one** rule and document it —
recommendation: round tax half-up, round change **in the customer's favour**
(never create a 1-riel shortfall the cashier cannot hand over). USD keeps 2dp.

### 6.3 Rate drift between cart and payment
The rate captured when the sale is completed is the only one that matters. A stale
rate must warn, not silently apply.

### 6.4 Refunds
Refund **per tender**: a bill paid Cash USD + KHQR KHR refunds each tender in its
own currency, up to what was taken on it. A single-currency refund for a
mixed-currency bill is how drawers stop balancing.

### 6.5 Shifts / Z-reports
Cash is counted **per currency**. The expected drawer is per currency; a single
converted figure cannot be counted against notes in two currencies.

### 6.6 Offline sales
Record tender currency + rate at capture; syncing later must not restate them.
A queued KHR sale replayed at a newer rate is wrong money.

### 6.7 Deposits and balances
Deposit and balance are separate payment intents with separate rates. A KHR
balance on a USD-priced reservation is a conversion, not a re-price.

### 6.8 Pure-KHR stores
A store priced in KHR with only a KHR link: all sales KHR, KHQR in KHR only, no
USD in the drawer. The USD link may be absent entirely.

### 6.9 Multi-store companies
The company enables currencies and holds a fallback link per currency; each store
prices in one. A company with one USD store and one KHR store is exactly why links
are per currency, not per company.

## 7. Current state in the code (verified)

| Piece | State |
|---|---|
| Store pricing currency | ✅ `Store.currency_code`; change refused unless enabled on the company (400 verified) |
| Company currencies + rates | ✅ `CompanyCurrency`, `ExchangeRate(rate Numeric(20,8))`, `multi_currency` plan gate |
| Per-tender rate snapshot | ✅ `Payment.exchange_rate` |
| Mixed tenders in the POS (cash/cash, cash/QR, two currencies) | ✅ tenders carry `method`, `currency_code`, `amount`; `changeCurrency` exists |
| One QR per sale | ✅ enforced (`khqrCount > 1` refused) |
| KHR payment links, one per currency | ✅ `aba_payway_links` map + settings pane + provider verification |
| Public order charged in the store's currency, KHR without a KHR link refused | ✅ (PR #921) |
| **Dual-only cap** | ❌ `enabled_codes` allows 20 |
| **Currency on the POS / deposit / balance mint sites** | ❌ still default to USD (three call sites) |
| **Refund-by-tender / per-currency drawer** | ⚠️ unverified — must be tested before a KHR merchant goes live |
| **Riel display in storefront + POS** | ❌ not built |

## 8. Rollout

| # | Branch | Scope |
|---|---|---|
| 0 | `docs/currency-policy` | this document |
| 1 | `fix/dual-currency-cap` | cap `enabled_codes` at 2 server-side + test; currencies-pane hint pointing at Bank & KHQR |
| 2 | `feat/pos-currency-threading` | pass the store's currency into the POS/deposit/balance `create_payment` sites; KHR store with no KHR link refuses with a clear message (same rule as the public path) |
| 3 | `test/refund-tender-and-drawer` | prove refunds mirror tenders and the drawer counts per currency; fix what the test finds |
| 4 | `test/reporting-currencies` | prove the tender breakdown splits by currency and the consolidated report never sums across currencies (§9.5) |
| 5 | `feat/khr-display` | ៛ in the storefront and POS (dual display, round to whole riel) |

Each ships independently; USD-only merchants see no change.

## 9. Reporting

### 9.1 The one rule

**Never sum money across currencies.** Every total is in one currency, or shown
side by side. `3,000 KHR + $3.00` is not a number, and a report that produces one
is wrong — this is the failure every multi-currency POS eventually ships.

### 9.2 Revenue is in the order's currency; payments are per tender

- **Revenue** uses the order's own `currency_code` — the price list the sale used.
  A store that switched USD→KHR mid-year has two groups of orders, and history is
  never re-converted.
- **Payments** are reported per tender: method × currency. A "KHQR total" that
  blends USD and KHR is an accounting error.
- The two connect through the rate snapshot on each payment (`Payment.exchange_rate`).

### 9.3 What each report must show

| Report | Currency handling |
|---|---|
| Sales summary | base (order currency); split by order currency if the store switched |
| Tender breakdown | **per currency × method** — Cash USD, Cash KHR, KHQR USD, KHQR KHR — never one blended "QR" figure |
| Z-report / shift | expected vs counted **per currency**; variance per currency |
| Refunds | per tender currency, proportional to what was taken on each |
| Tax report | base, plus a KHR conversion at a **declared rate** if the filing requires riel (GDT filings are in ៛) |
| Product / margin | base only (prices and costs are base) |
| Consolidated (multi-store) | per-currency columns, or converted with the rate **and date** stated |

### 9.4 Edge cases

- **Currency switch mid-period:** split the period by order currency. Do not
  convert old orders at today's rate.
- **Rounding:** round once at the total, never per line, or the totals drift by a
  riel per row.
- **FX variance:** the customer pays KHR at the snapshot rate; the bank converts at
  its own. The difference is FX exposure, **not revenue** — report it separately or
  not at all, but never adjust the sale.
- **Refund in another currency:** show the refund currency alongside the original
  tender, not instead of it.
- **Consolidated across stores with different currencies:** a single "total" only
  means something with a stated conversion; otherwise show per-currency columns.

### 9.5 Current code and the risk to verify

`report_summary`, the consolidated report, refunds and shifts all exist, and the
data needed is there (`Order.currency_code`, `Payment.exchange_rate`). The two
things to **prove with a test**, not assume:

1. the consolidated report does not sum across stores in different currencies;
2. the tender breakdown splits by currency, not just by method.

## 10. Open decisions

1. **Tender-line cap** — allow cash+cash+QR (3 lines), or cap at 2 lines? Recommend
   3, because splitting cash across two currencies is a real counter behaviour.
2. **KHR rounding direction** for change — customer's favour (recommended) vs
   banker's rounding.
3. **Rate source** — manual per company (today) vs a Bakong mid-rate feed. Manual
   first; a feed is an additive change.
4. **Third currency** — explicitly refused for now; if ever, it is a new decision,
   not a config toggle.

## 11. Impact analysis (measured 2026-10-20)

### 11.1 Surface

| Area | `USD` literal hits | Note |
|---|---|---|
| `chmabapos_api/app` | 66 | often "default when unset" (fine), sometimes a hard assumption (not) |
| `apps/web/src` | 56 | POS tenders, receipts, report formatting |
| `apps/android` | 42 | second POS client — see `apps/android/DESIGN_GUIDE.md` |
| `apps/ios` | 12 | third client, and **its CI job does not compile it** — see `apps/ios/README.md` |
| `apps/storefront` | 6 | display only |

Money aggregation / rounding sites in the API: **93** (`func.sum` and
`Decimal("0.01")`), spread across `v1.py` (9), `store_notifications.py` (7),
`telegram_digest.py` (3), `orders.py` (1), `support_tools.py` (1) plus inline
rounding in the write paths.

### 11.2 Already correct

- The **consolidated report** converts each order to the company base with
  `get_exchange_rate(...)` and quantizes with the currency's own `decimal_places`
  (`Decimal("1")` for riel). The worst case — adding riel to dollars — is avoided
  there.
- Some aggregation already **groups by `Order.currency_code`** (e.g. the
  dashboard's gross rows).

### 11.3 Bugs found — fix before enabling KHR

**B1. Customer `total_spent` adds riel to dollars.** `v1.py:9544` sums
`Order.total` across every store in the company with no currency grouping and no
conversion. A customer who spent $3 and 3,000៛ reads **3,003**. Wrong today,
before any KHR work.

**B2. Reports are not reproducible.** `v1.py:9364` converts using
`get_exchange_rate(..., at=order_date)` — the **rate table** — rather than the
`Payment.exchange_rate` snapshot taken with the sale. Editing or backfilling a
historical rate changes last month's revenue on a re-run.

### 11.4 Other impact areas

| Area | Risk | Why |
|---|---|---|
| Rounding sweep | **high** | 93 sites use `Decimal("0.01")`; KHR has no subunit, so each must use the currency quantum or totals drift a riel per line |
| Tender breakdown / drawer | **high** | reports group by method today; they need **method × currency**, and the drawer is counted per currency |
| Refunds | **high** | must mirror tenders; unverified |
| GDT CSV export | **medium‑high** | a **legal** tax surface; it must state its currency and rate |
| Notifications / digests / sale emails | medium | 10 money sums in those modules can mix currencies in an email |
| Android + iOS | medium | 54 `USD` hits across the two; iOS can only be verified on a device |
| Tests / fixtures | low | many assume USD and will mask regressions |

### 11.5 Revised order (supersedes §8)

1. `fix/customer-total-currency` — B1
2. `test/reporting-reproducible` — B2
3. `refactor/money-quantum` — one `money_quantum(currency)` helper; sweep the 93 sites
4. `test/refund-tender-and-drawer`
5. `fix/dual-currency-cap`
6. `feat/pos-currency-threading`
7. `feat/khr-display`, then the Android and iOS sweeps (+ a device check for iOS)
8. GDT CSV currency review

Rationale: the two bugs are independent of KHR and cheap to fix, and a wrong total
is worse than a missing feature. Fixing them first also means the later changes are
built on numbers that are already correct.

### 11.6 Client-specific notes

- **Android** — `apps/android/DESIGN_GUIDE.md`, section "Currency & tenders (USD + KHR)".
- **iOS** — `apps/ios/README.md`, same section, including the device-check constraint.
- **Web** — `apps/web/src/lib/money.js` owns currency-precision entry (`moneyInput`), so a
  KHR cash field prefills `3666`, never `3666.00`, and the amount sent for a KHR tender is
  already whole.

### 11.7 GDT CSV export — reviewed

The export is **store-scoped** and writes **one row per paid invoice with its own
`currency` column**, so a company with a USD store and a KHR store cannot have its
takings summed by accident — the two produce two files. There is no rate column and
none is needed: a single-currency file states its currency, and any filing
conversion is the step §9 already describes (a declared rate, recorded).

One defect was found and fixed: amounts were printed with two decimals regardless
of currency, so a riel invoice read `3333.00 KHR` — a subunit the currency does not
have. The export now prints each figure in the store currency's own precision.
`tests/test_gdt_export.py` pins it, alongside the existing BOM check.

### 11.8 Client display audit — all three are correct

Swept rather than assumed:

| Client | Formatter | KHR behaviour |
|---|---|---|
| Web | `formatCurrencyAmount` (`components/ui.jsx`) for display; `lib/money.js` for entry | `Math.round(…)` + `៛`; entry uses `moneyInput`, so `3666`, never `3666.00` |
| Storefront | `Intl.NumberFormat` with `currency: code` (`app/lib/api.js`) | ICU gives KHR zero fraction digits; `toFixed(2)` is only the catch‑all when `Intl` throws |
| Android | `Store.money(value, currency)`; `POSScreen` delegates to it | `"%,.0f"` + `៛` — the sign follows the figure, as riel is written; THB and USD keep two decimals |
| iOS | `money(_:code:)` via `NumberFormatter.currencyCode` | ICU renders riel whole. `priceLabel`'s `$%.2f` is **billing plan pricing** — platform USD, not store money |

The "54 `USD` hits" the impact analysis counted are **defaults for an unset store
currency** and platform prices, not display rules. The `toFixed(2)` calls left in the
web POS are arithmetic (tax, totals, API payloads) over amounts that are already whole,
not formatting.

So no client needed a display change. The visible defects were server‑side (checkout,
drawer, GDT export), and the one client defect was **entry** — the web collect‑balance
dialog prefilling hundredths for a KHR balance.

### 11.9 Refund currency — decided, and why

A refund is denominated in the **order's currency**, which is the store's, and the
drawer counts the converted base amount on both sides:

- a USD store takes 40,000 KHR for a $10 sale at 4,000;
- the cash refund is **$10.00**, not 40,000 KHR;
- the shift shows `cash_received 10.00`, `cash_refunds 10.00`, `expected_cash 0.00` —
  an empty drawer reconciles.

`tests/test_refund_tender_currency.py` pins it.

**Why not refund in the tendered currency.** "Mirror the tender" sounds closer to
what happened at the counter, but it is a feature, not a formatting fix:

| Cost | Detail |
|---|---|
| Schema | a `refund_tenders` table (currency, amount, rate); a refund is one row with one `currency_code` today |
| Drawer | `cash_received`/`cash_refunds` are base totals by policy ("one base per store", §9); per‑currency counting needs a second reconciliation model |
| Clients | web, Android and iOS each show one refund amount and would need a currency choice |
| Rates | the refund must use the rate at **sale** time or the rate now — either way it becomes a dated price |

Until a merchant asks, the base‑currency refund is the coherent choice: it keeps the
drawer reconcilable and the books in one currency. The limit to state honestly to a
merchant is narrow but real: **if the cashier hands back riel, the drawer model does
not know.**

## 12. Out of scope

- Multi-currency *pricing* (two price lists per product).
- Cross-currency settlement at the provider (each link settles in its own currency).
- Currency conversion for customers at a rate we choose (we convert the tender, not
  the price).
- Cryptocurrencies and any currency beyond USD/KHR.
