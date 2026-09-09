# Chmaba API v1

FastAPI API for Chmaba cloud POS. PostgreSQL is the source of truth. Frontend integration comes after this contract is stable.

## Stack

- FastAPI + Pydantic v2
- SQLAlchemy 2 async + asyncpg
- Alembic migrations
- PostgreSQL 16
- JWT access tokens
- MailHog SMTP in development
- CutLuy KHQR checkout and signed webhooks

## Local setup

1. Create virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r chmabapos_api\requirements.txt
```

2. Copy `chmabapos_api\.env.example` to `chmabapos_api\.env` and update secrets.

3. Create database `chmaba_v1` if it does not exist, then run migrations. Existing `chmaba` schema is left untouched:

```powershell
python chmabapos_api\scripts\create_database.py
alembic -c chmabapos_api\alembic.ini upgrade head
python chmabapos_api\scripts\seed.py
```

4. Start API:

```powershell
uvicorn app.main:app --reload --app-dir chmabapos_api
```

API docs: `http://localhost:8000/docs`

Health: `http://localhost:8000/api/v1/health`

## Frontend integration

The Vite app defaults to `http://127.0.0.1:8000/api/v1`. Override with:

```powershell
$env:VITE_API_URL="http://127.0.0.1:8000/api/v1"
npm run dev
```

Authenticated workspace screens use PostgreSQL for products, stock, orders, reports, team, billing, currencies, and exchange rates. `See live demo` on the landing page remains a local UI-only preview.

## Auth development flow

Sign-up uses email confirmation codes (Model A): the account starts unverified and
cannot sign in until it is confirmed.

- `POST /api/v1/auth/register` emails a 6-digit confirmation code. In development it also returns it as `dev_verification_token`, so automated tests and local scripts can confirm the account without parsing MailHog.
- `POST /api/v1/auth/verify-email` accepts the code and marks the account verified; login then returns a JWT bearer token.
- `POST /api/v1/auth/resend-verification` issues a fresh code for an unverified account (previous codes are invalidated). It responds the same for unknown/already-verified emails to avoid leaking which addresses exist.

Login for an unverified account returns `403`, which the web app uses to route the user to the confirmation-code screen.

## CutLuy

`CUTLUY_MODE=mock` creates local pending checkout records with fake QR data. Set `CUTLUY_MODE=live` and `CUTLUY_API_KEY` for real CutLuy payments. Secret keys stay server-side. `POST /api/v1/webhooks/cutluy` verifies `X-CutLuy-Signature` before activating a paid plan or completing a KHQR order.

## Multi-currency POS

The store keeps one base currency for reporting and accounting. Exchange rates are merchant-configured and mean `1 base currency = N quote currency`. Example: `1 USD = 4,000 KHR`.

1. Enable currencies for the company:

```http
PUT /api/v1/settings/currencies
Authorization: Bearer <token>

{"primary_code":"USD","enabled_codes":["USD","KHR"]}
```

2. Add the effective-dated rate:

```http
POST /api/v1/exchange-rates
Authorization: Bearer <owner-token>

{"base_currency_code":"USD","quote_currency_code":"KHR","rate":"4000"}
```

3. Send multiple tenders at checkout. A `$4.95` order can receive `$10.00` plus `10,000 KHR` (`$2.50`), for `$12.50` tendered and `30,200 KHR` change at this rate:

```http
POST /api/v1/orders
X-Store-ID: <store-id>
Authorization: Bearer <token>

{
  "items":[{"product_id":"<product-id>","quantity":1}],
  "tenders":[
    {"method":"cash","currency_code":"USD","amount":"10.00"},
    {"method":"cash","currency_code":"KHR","amount":"10000"}
  ],
  "change_currency_code":"KHR"
}
```

Each order stores original tender amounts, converted base amounts, and rate snapshots. Future rate changes do not rewrite past receipts. KHQR remains one exact USD tender in v1 because CutLuy settles payment amounts in USD; mixed cash/card settlement supports enabled currencies.
