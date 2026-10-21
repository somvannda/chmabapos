# Shopper accounts and profiles

The customer-facing account on `shops.chmaba.com`: one platform-level shopper
identity, separate from merchant/staff users. This is the guide for what exists,
what the best practice is, and what is deliberately not built yet.

## Model

- **`shopper_accounts`** — one row per person, across every store on Chmaba.
  Never counted as a plan seat, never able to reach the POS or admin.
- **`shopper_sessions`** — revocable sign-ins. Signing out clears the token and
  revokes the session server-side.
- **`shopper_email_codes`** — hashed, single-use email codes.
- **`shopper_addresses`** — saved addresses, cascade with the account.
- **Relationships** — orders, conversations and the merchant's `customers` CRM
  rows carry `shopper_id`; each store sees only its own relationship.

Sign-in methods: email one-time code, Google (ID token), Telegram. No passwords.

## Shipped

- Guest-first browsing, chat and checkout; an account is never required.
- Sign in and Create account modes, with full name and optional phone on sign-up.
- Header account menu: full name/avatar, Orders, Messages, Addresses, Profile,
  Sign out.
- Claiming guest chat threads on sign-in, across stores.
- Profile editing (name, phone), marketing opt-in toggle.
- Saved addresses: create, edit, delete, default; first address is the default.
- Data export: JSON download of profile, addresses, orders and conversations.
- Account deletion: requires typing the account email; deletes the account,
  sessions, codes and addresses; anonymises conversations and the merchant CRM
  row; detaches held orders. Financial records stay, without the identity.
- Google sign-in reads the public client ID from `/public/config`, so the same
  OAuth client is used as the POS; `https://shops.chmaba.com` must be an
  authorized JavaScript origin.

## Best practices applied

- Passwordless auth; no password storage or reset flow.
- Marketing consent is separate from account creation, opt-in by default off,
  timestamped, and mirrored to `email_suppressions`.
- Export and delete are self-service and do not require support.
- Deletion requires an explicit confirmation and revokes sessions immediately.
- No merging of accounts by an unverified phone or email; claiming is by the
  thread token or the authenticated account.
- Mobile-first inputs (16px) and safe areas; the account page uses a desktop
  sidebar and mobile tabs.

## Backlog

### 1. Phone verification — blocked on an SMS provider

There is no SMS service configured in the API. A real verification needs:

1. A provider (Twilio, MessageBird, AWS SNS, or a local gateway) and credentials.
2. `phone_verification_codes` (hashed code, expiry, attempts, used_at) and a
   send endpoint with rate limits.
3. `phone_verified_at` on `shopper_accounts`; the client shows a "Verify" action
   in Profile and a "Verified" badge.
4. Only after that, allow phone-based guest continuity or account recovery.

Do not implement this with an email code — that verifies the account, not the
phone number, and would let someone mark a phone they do not own as verified.

### 2. Delivery at checkout

Order records already have `order_type` and `delivery_address`, but the public
storefront checkout only offers pickup. To make saved addresses earn their
place:

- Add a pickup/delivery choice to the cart.
- Send `order_type` and the selected address in `PublicOrderSubmitRequest`.
- Store the address on the held order and show it in the merchant's order view.
- Keep guest checkout; a saved address is a convenience, not a requirement.

### 3. Other recommended features

- **Saved payment methods** via the payment provider (tokenized; never store card
  numbers).
- **Apple sign-in** alongside Google.
- **Session management:** list active devices and "sign out everywhere".
- **Marketing consent history:** append-only rows rather than one timestamp, for
  audit and regional consent rules.
- **Account recovery:** a verified phone or email change flow; currently a lost
  email is a lost account.
- **A "remember me" choice** with session lifetime, especially for shared phones.
- **Order history detail:** reorder, download receipt, per-order chat.
- **Localization:** account pages in Khmer, including validation messages.
- **Metrics:** sign-in conversion, account creation, repeat purchase, profile
  completion, deletion/export volume.
- **Guest order claim by verified email** (already partially done for orders).

## API surface

- `POST /public/auth/email-code`, `POST /public/auth/verify`
- `POST /public/auth/google`, `POST /public/auth/telegram`
- `GET/PATCH /public/auth/me`
- `POST /public/auth/logout`
- `GET /public/auth/orders`
- `GET /public/auth/chat/conversations`
- `GET/POST/PATCH/DELETE /public/auth/addresses`
- `GET /public/auth/export`
- `POST /public/auth/delete-account`
- `GET /public/config` (public Google client ID)

## Rules for future work

- Never put shopper rows in `users`; plan seats and staff administration depend
  on the two being separate.
- Never authorise a shopper token on a staff endpoint, or the reverse.
- Keep store data scoped: a merchant must not see another store's relationship
  with the same shopper.
- New endpoints that change personal data need an export/delete story.
- Migrations chain to one Alembic head and regenerate `openapi.json` +
  `packages/api-client/src/schema.d.ts`.
