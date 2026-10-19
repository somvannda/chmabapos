# Storefront go-live runbook

Everything for the public storefront is built and deployed **except the host
itself**. This is the cutover, in order, with the failure modes that are easy to
misdiagnose.

Related: `docs/marketplace-storefront-plan.md` (§5.1 host, §10 deployment),
`deploy/nginx.conf`, `deploy/docker-compose.prod.yml`.

## Why this is staged

`VITE_STOREFRONT_URL` is the switch that moves every store link onto the branded
URL. While it is blank:

- the marketing header has **no** Stores link,
- Settings → Online ordering shows the tokenised link,
- `chmaba.com/order/<token>` serves the menu inline instead of redirecting.

Blank is the safe state. Nothing needs to be reverted if the cutover is delayed.
**Do not set it before the host answers over HTTPS.**

## 1. DNS

Create an `A` (or `CNAME`) record for `shops.chmaba.com` pointing at the same
origin as `chmaba.com`, proxied through Cloudflare.

Verify:

```bash
dig +short shops.chmaba.com
```

## 2. Certificate — the step most likely to go wrong

The origin terminates TLS with the certificate mounted at `/etc/nginx/certs/`
(Cloudflare Origin CA). It must be **valid for `shops.chmaba.com`** — either an
explicit SAN or a wildcard such as `*.chmaba.com`.

Check the SAN on the certificate actually in use:

```bash
openssl x509 -in deploy/certs/fullchain.pem -noout -text \
  | grep -A1 "Subject Alternative Name"
```

If `shops.chmaba.com` is absent, obtain a certificate that covers it and replace
both files, then redeploy.

**Two traps here, both silent:**

- **`nginx -t` does not fail on a hostname mismatch.** It loads the config fine.
  A successful deploy is therefore *not* evidence that the certificate is valid
  for the host.
- With Cloudflare SSL mode **Full (strict)**, a missing SAN appears as a **526**
  at the edge, not as an obvious origin error.

So the only real check is an HTTPS request (step 3).

## 3. Deploy and verify the host

```bash
docker compose -f deploy/docker-compose.prod.yml up -d --build
```

Then, from outside the server:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://shops.chmaba.com/
curl -sSI https://shops.chmaba.com/ | head -1
```

Expected: `200`, no certificate warning. A `526` means the origin certificate
does not cover the host (step 2). A `502` means nginx reached no storefront
container — check the `storefront` service is healthy.

Confirm a real store renders, using a store that has online ordering enabled:

```bash
curl -sS https://shops.chmaba.com/<company-slug>/<store-slug> | grep -o '<title>[^<]*</title>'
```

The title should be the store's name, not "Store not found".

Also confirm the directory and the crawler files:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://shops.chmaba.com/stores
curl -sS https://shops.chmaba.com/robots.txt
curl -sS https://shops.chmaba.com/sitemap.xml | head -5
```

## 4. Flip the switch

In `deploy/.env` on the server (and wherever the front image is built):

```
VITE_STOREFRONT_URL=https://shops.chmaba.com
```

`VITE_*` values are inlined **at build time**, so the front image must be
rebuilt — editing `.env` alone changes nothing:

```bash
docker compose -f deploy/docker-compose.prod.yml up -d --build
```

## 5. Post-cutover checks

- Marketing header now shows a **Stores** link, opening the directory in a new tab.
- Settings → Online ordering shows `https://shops.chmaba.com/<company>/<store>`.
- All stores list → **Store link** opens the branded page.
- `chmaba.com/order/<token>` **redirects** to the branded page. This matters:
  printed table QR codes encode that URL and must keep working.
- Place a test order end to end and confirm it reaches the Kitchen board.

## Rollback

Set `VITE_STOREFRONT_URL` back to empty, rebuild the front image, and redeploy.
Every link returns to the tokenised URL, which was never removed. No data
migration is involved, and the storefront host can stay up or be taken down
independently.

## Known gaps at go-live

- **Checkout is USD only.** KHQR is USD-only today, so a merchant pricing in riel
  cannot take online payment. See the plan's §13.1.
- **Shopper accounts exist** (email code, Google, Telegram, order history), and
  checkout stays guest-first. There is **no guest→account merge yet**: a shopper
  who bought as a guest before signing in does not see those orders.
- There is **no admin moderation UI beyond list/unlist** and no directory filters.
- The deploy pipeline's smoke check covers `chmaba.com` and `admin.chmaba.com`;
  add `shops.chmaba.com` to it once this host exists.
