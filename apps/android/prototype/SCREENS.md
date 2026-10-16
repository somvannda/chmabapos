# Chmaba POS — Android Screen Inventory (A→Z)

Derived from the live web app: `apps/web/src/routing.js`, `App.jsx`, `features/*`, `components/ui.jsx`, `styles.css`.

## Design tokens (lifted from web, must match exactly)

| Token | Web value | Usage |
|---|---|---|
| Brand purple | `#6957f5` | Primary actions, active states |
| Purple hover | `#5845e7` / `#7b6bf7` | Button hover |
| Brand lime | `#c4f27c` | Accent, dark-panel highlights |
| Ink | `#17181c` / `#202128` | Headings |
| Body text | `#4f5059` / `#565762` | Body |
| Muted | `#898a95` / `#92939d` | Secondary |
| Faint | `#a1a2ab` / `#b0b1ba` | Captions |
| Page bg | `#f7f7fa` / `#fafafd` | Backgrounds |
| Surface | `#ffffff` | Cards |
| Border | `#e9e9ef` / `#dfdfe8` | Card + input borders |
| Success | bg `#edf9e4` fg `#4f8b32` | Paid / in stock |
| Warning | bg `#fff6df` fg `#ad7d1c` | Low stock / pending |
| Danger | bg `#fff0ee` fg `#c2564b` | Failed / destructive |
| Violet | bg `#f0efff` fg `#6555df` | Soft actions / badges |
| Info | bg `#eaf4ff` fg `#3579b8` | Informational |
| Dark bg | `#111114` | Dark mode |
| Dark surface | `#1a1b20` | Dark cards |
| Radius | 8 / 12 / 16 / 24 / 28 | Components |
| Shadow soft | `0 14px 40px rgba(28,31,42,.07)` | Cards |
| Shadow panel | `0 28px 70px rgba(28,31,42,.12)` | Modals / auth shell |
| Font | `Inter, ui-sans-serif, system-ui` | All text |

## Screen list

### A. Boot & Auth (7)
1. **Splash** — logo, tagline, spinner
2. **Login** — email, password, remember, forgot
3. **Signup** — name, email, phone, password, confirm
4. **Verify email** — 6-digit OTP groups, resend
5. **Forgot / reset password** — email → new password
6. **404 Not found** — illustration, back home
7. **Admin access denied** — guard screen

### B. Onboarding / Setup (4)
8. **Setup · Company** — company, store, country, currency
9. **Setup · Questions** — business type (drives feature packs)
10. **Setup · Plan** — free / starter / pro, billing cycle
11. **Setup · Ready** — success + enter workspace

### C. Core app (bottom nav: Home · POS · Orders · More) (12)
12. **Dashboard** — greeting, 4 metric cards, sales chart, top products, recent transactions, quick actions
13. **POS (make a sale)** — search + scan, category chips, product grid, cart sheet, tenders
14. **Orders** — filter tabs, stat row, order rows
15. **Order detail** — lines, totals, payments, refund/cancel/collect actions
16. **Customers** — search, stats, list, add customer
17. **Customer detail** — orders, total spent, loyalty points
18. **Products (catalog)** — stats, grid/list, edit/add
19. **Product editor** — name, SKU, price, cost, tax, category, image, variants, stock, serials
20. **Categories** — parent/child tree, add/rename
21. **Inventory** — stock levels, adjust, receive stock
22. **Purchasing** — purchase orders, receive
23. **Reports** — gross/net/transactions/refunds, sales-by-day, payment breakdown, top categories

### D. Account & admin (6)
24. **Suppliers** — list, add, contact
25. **Team** — members, roles, invite
26. **Activity** — audit log
27. **Billing & plans** — current plan, upgrade, cycle, invoices
27b. **Upgrade · Free plan** — free-user status, cycle chips, a peeking plan carousel (Free / Starter / Pro) with one CTA. No arrow buttons: the next card's 45px peek is the affordance. Carries no settlement copy — the ABA PayWay link is configured in payment settings, not here.
28. **Settings** — store, currency, tax, receipts, hardware, theme
29. **Help / Support** — help articles, AI assistant, ticket

### E. Surfaces & overlays (6)
30. **Customer display** — external screen snapshot (cart/payment/paid)
31. **Payment sheet** — Cash / KHQR, tenders, change
32. **KHQR scan result** — QR, expiry, polling status
33. **Modifier picker** — options with price deltas
34. **Combo builder** — choose-your-own steps
35. **Receipt** — thermal 80mm preview + print actions

## Android adaptation rules (visual stays, interaction changes)

| Web pattern | Android pattern |
|---|---|
| Left sidebar nav (`ADMIN_NAV_ITEMS`) | Bottom nav + "More" drawer |
| Desktop 3-column POS | Grid + cart **bottom sheet** |
| Centered `Modal` | `ModalBottomSheet` (full-width, drag handle) |
| Hover states | Ripple + pressed elevation |
| Tables (`mobile-table`) | Card rows / `LazyColumn` |
| 32–40px controls | ≥48dp touch targets |
| Keyboard search | + camera scan FAB |
| `window.open` customer display | Cast/secondary-display intent |

**Never change:** colors, type scale, radii, icon set (lucide→Material equivalents), wording/copy, status tones.
