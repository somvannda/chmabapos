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
| 4 | `feat/khr-display` | ៛ in the storefront and POS (dual display, round to whole riel) |

Each ships independently; USD-only merchants see no change.

## 9. Open decisions

1. **Tender-line cap** — allow cash+cash+QR (3 lines), or cap at 2 lines? Recommend
   3, because splitting cash across two currencies is a real counter behaviour.
2. **KHR rounding direction** for change — customer's favour (recommended) vs
   banker's rounding.
3. **Rate source** — manual per company (today) vs a Bakong mid-rate feed. Manual
   first; a feed is an additive change.
4. **Third currency** — explicitly refused for now; if ever, it is a new decision,
   not a config toggle.

## 10. Out of scope

- Multi-currency *pricing* (two price lists per product).
- Cross-currency settlement at the provider (each link settles in its own currency).
- Currency conversion for customers at a rate we choose (we convert the tender, not
  the price).
- Cryptocurrencies and any currency beyond USD/KHR.
