# Auth abuse hardening

Status: first hardening slice merged (#1071) and deployed to production at
`843929c`; the Cloudflare-only origin allowlist was applied on 19 Nov. The
remaining items are tracked below with acceptance checks.

Scope: `chmabapos_api` auth surface, `deploy/nginx.conf`, `apps/admin` user status.

## 1. What happened

On 18–19 November 2026 a scripted campaign created a series of probe accounts
against production. The addresses followed a pattern rather than a customer
signup:

| Pattern | Examples | Result |
|---|---|---|
| Reserved test domains | `artex.probe1@example.com`, `probe1@example.com`, `audit31000+…@example.com`, `qa-…@example.org` | Registered, never verified, never signed in |
| Public/disposable inboxes | `artex31061a/b@mailinator.com` | Registered, never signed in |
| Public/disposable inboxes | `artx31061@euploading.com`, `ubalbeldwv@euploading.com`, `artx31196+180903@euploading.com` | **Two signed in**; one created a company |
| Admin-sounding names | `Probe Admin`, `Qa Adm` | No effect: both remained `platform_role = null` (Tenant user) |

The account IDs (`30788`, `31000`, `31061`, `31196`), the A/B/C names and the
plus-aliases show deliberate iteration: test a domain, see whether the code
arrives, move to the next provider. The `+` alias and the names `Probe Admin` /
`Qa Adm` also test whether the display name or address shape changes
authorization. It does not: `RegisterRequest` has no role field and Pydantic
ignores unknown fields.

One probe account (`artx31061@euploading.com`) completed onboarding and created
a company. That is the highest-risk row and must be inspected, suspended and
removed together with its company.

The actor also requested a password reset for `duke@chmaba.com`, a platform
admin.

### Confirmed evidence (19 Nov)

The actor reached the origin directly at `163.245.204.122` with `curl/8.13.0`
(HTTP/1.1, no `X-Forwarded-For`), alongside Cloudflare-proxied requests carrying
rotating `203.x` values in `X-Forwarded-For`. The consistent real egress is
**66.163.112.172** (`172-112-163-66.clients.gthost.com`, AS63023 GTHost,
Phoenix, Arizona): external hosting infrastructure, not a customer.

This is the critical infrastructure finding: **Cloudflare can be bypassed by
hitting the origin IP directly**, and `CF-Connecting-IP` can then be spoofed.
The IP was temporarily dropped in `DOCKER-USER`; the durable fix is a
Cloudflare-only origin allowlist (or a Tunnel) plus a Cloudflare WAF block.

Duke's reset **did not succeed**: there is no `user.password_reset` event, the
11 reset requests retired one another or expired unused, duke signed in
successfully after the attempt, and no unknown session exists. The attacker's
own reset (`ubalbeldwv@euploading.com`) did complete, which is how they tested
the flow.

Verification was passed with disposable inboxes, not brute force:
`artx31061@euploading.com` registered at 16:06:21 and verified at 16:06:40;
`ubalbeldwv@euploading.com` registered at 15:25:39 and verified at 15:26:14.

`artx31061@euploading.com` created company **Artex Research 31061**, store
**Artex Store 31061** and 3 products on the free plan. It then made 12 AI
support calls and 13 no-match questions, including attempts to print the system
prompt, provider API key, base URL and environment variables. Every attempt was
refused; no secret or cross-tenant data was disclosed. The company, store and
the 14 probe users were suspended and their sessions revoked; all rows were
kept for evidence.

## 2. Root causes

1. **Registration is open and unthrottled.** `POST /api/v1/auth/register` has no
   rate limit, no invitation gate and accepts any syntactically valid email.
   `User.is_active` defaults to `true`, so the admin list shows "Active" before
   the address is verified.
2. **Turnstile is configured in code but not enabled in production.** The
   production web bundle contains no Turnstile widget and the API accepts a
   registration without a token. `TURNSTILE_SECRET_KEY` and
   `VITE_TURNSTILE_SITE_KEY` are blank in `deploy/.env`.
3. **The only auth limiter covered `/api/v1/public/`.** `app/main.py` limited
   storefront traffic; nothing limited `/api/v1/auth/*`.
4. **The verification code is checked globally.** `POST /auth/verify-email`
   looks up `EmailVerificationToken.token_hash` without binding the attempt to
   the user or email. A six-digit code (`app/security.py`) has only 1,000,000
   values and there was no attempt limit, so the code space can be walked by a
   script. The successful sign-ins in this campaign used disposable inboxes
   instead, but the endpoint is independently exploitable.
5. **Public inboxes are treated as proof of identity.** `mailinator.com` and
   `euploading.com` are readable by anyone; a verification code sent there
   proves nothing about a real merchant.
6. **Suspended accounts could still call login.** `login` did not check
   `is_active`; it issued a session, and the token only failed on the next
   authenticated request.
7. **The API cannot see the visitor IP.** nginx forwarded `$remote_addr`, which
   is the Cloudflare edge, and the app trusted it. Per-IP limits and session
   `ip_address` therefore describe Cloudflare, not the caller.

### Was the admin reset successful?

The reset link is a 32-byte opaque token (`secrets.token_urlsafe(32)`), stored
only as SHA-256, expires in 30 minutes, is single-use, and is built from the
fixed `settings.frontend_url` (no Host-header poisoning). A request alone does
not change the password. **Unless the actor can read `duke@chmaba.com`'s inbox,
the reset did not complete.**

Confirm with the runbook in §4. A completed reset is visible as a
`user.password_reset` activity, a used `password_reset_tokens` row, every duke
session revoked, and a "Password reset" Telegram message. A request alone is
`user.password_reset_requested`.

### How did they "bypass" email verification?

For the accounts that signed in, they most likely did **not** bypass it: they
used a disposable inbox and read the code. The `example.com` / `example.org`
accounts never signed in because those domains cannot receive mail.

There are nevertheless real bypass paths in the code:

- **Code brute force** — six digits, global token lookup, no attempt limit. If
  the actor requests codes for several accounts they own, the expected search is
  `1,000,000 / pending_tokens`. A few dozen accounts makes this minutes of work.
- **`ENVIRONMENT` misconfiguration** — `register` returns
  `dev_verification_token` when `environment` is `development` or `test`. If a
  production container ran with the wrong value, the code is handed to the
  caller. Verify the running container.
- **Google sign-in** — a verified Google account is trusted immediately. This is
  legitimate, but it skips the emailed code.
- **Invitation acceptance** — `accept_team_invitation` creates the user with
  `is_email_verified=True` and an immediate session. The invitation token is
  emailed, so it still proves inbox control, but it bypasses the signup code.
- **Password reset is not a verification bypass** — the token is strong. A reset
  request alone cannot verify an account or change a password.

## 3. Implemented in this slice

- [x] **Rate-limit every auth POST** in `app/main.py`:
  login/Google 10/min, register 5/hour, verify 10/min, resend 3/hour,
  reset request 3/hour, reset confirm/validate 10/hour. Returns `429` with
  `Retry-After`.
- [x] **Per-address login lockout** in `login`: five attempts per address in
  fifteen minutes, cleared by a successful sign-in, so one person's typos do not
  lock out a shared office IP. Configurable with
  `AUTH_LOGIN_FAILURE_LIMIT` / `AUTH_LOGIN_FAILURE_WINDOW_MINUTES`.
- [x] **Per-address email-bomb limits** on resend-verification (1/minute) and
  password-reset requests (3/hour), with the same vague response so the limit
  cannot be used to enumerate accounts.
- [x] **Suspended accounts are refused at login** with `403`, not just on the
  next authenticated request.
- [x] **Reserved and disposable domains rejected at registration in
  production** (`app/services/email_policy.py`): `example.com`/`example.org`,
  `localhost`, `.test`, plus the common disposable providers including
  `mailinator.com` and `euploading.com`. The test/development environments keep
  accepting `example.com` because the API and Playwright suites depend on it.
- [x] **Real visitor IP** (`app/services/client_ip.py`, `deploy/nginx.conf`):
  nginx fills `X-Real-IP` from `CF-Connecting-IP`; the app uses it for rate
  limits, session rows and new-sign-in notices.
- [x] **Admin list distinguishes Active from Unverified**, and the user detail
  says "Active · unverified" so the list cannot be mistaken for an approved
  account.
- [x] **Tests** (`chmabapos_api/tests/test_auth_hardening.py`) for reserved
  domains, suspended login, login lockout, register throttling and client-IP
  resolution.
- [x] **E2E/dev limits disabled explicitly** in the Playwright API server, the
  same way the public limits already were, so the suite's many sign-ups do not
  flake.

## 4. Runbook: contain this incident

### 4.1 Preserve evidence

- Export the Admin → Users CSV.
- Export `platform_activities`, `auth_sessions`, `password_reset_tokens`,
  `audit_logs` and the probe company's rows.
- Keep nginx access logs for 18–19 November.

### 4.2 Check the duke reset

```sql
select event_type, created_at, details
from platform_activities
where email = 'duke@chmaba.com'
order by created_at desc
limit 50;

select id, created_at, expires_at, used_at
from password_reset_tokens
where user_id = (select id from users where email = 'duke@chmaba.com')
order by created_at desc;

select id, user_agent, ip_address, created_at, last_used_at, revoked_at
from auth_sessions
where user_id = (select id from users where email = 'duke@chmaba.com')
order by created_at desc
limit 20;

select action, entity_type, entity_id, details, created_at
from audit_logs
where actor_user_id = (select id from users where email = 'duke@chmaba.com')
order by created_at desc
limit 50;
```

- **Only `user.password_reset_requested`** → request only; no password change.
- **`user.password_reset` + token `used_at`** → the reset completed. Treat the
  admin account as compromised.

If compromised:

1. Reset duke's password from a clean device; revoke all sessions.
2. Rotate `JWT_SECRET`, then revoke sessions again (the JWT only shortens the
   access window; refresh sessions live in the database).
3. Rotate every secret an admin can reveal: ChmabaPay, SMTP/Resend, AI provider,
   Telegram bot.
4. Audit `audit_logs`, new `platform_role` values, plan changes and secret
   reveals.
5. Add 2FA before restoring normal admin use.
6. Brief support: a live tenant may attempt live-chat social engineering.

### 4.3 Suspend and remove

- Suspended on 19 Nov: all 14 probe users, plus company **Artex Research 31061**
  and store **Artex Store 31061**. All sessions were revoked.
- Suspension is enforced by `get_current_user` (`is_active` is checked on every
  authenticated request), so existing access tokens stop working immediately.
- The rows and the company's 3 products were kept for evidence. Export them
  before adding an admin delete action and removing the company.

### 4.4 Determine the source

The origin is directly reachable, so the nginx log contains two kinds of rows:

- Cloudflare-proxied requests: `$remote_addr` is a Cloudflare edge, and the
  last `X-Forwarded-For` value is the client address;
- direct requests: `$remote_addr` is the client and `X-Forwarded-For` is empty.

In this incident the actor used both, with `66.163.112.172` (GTHost) as the
consistent egress and rotating `203.x` values in `X-Forwarded-For`. Use
**Cloudflare → Security → Events** (or Logpush) filtered to the same paths to
confirm the edge view, and block the IP/ASN at the edge. A burst of
`verify-email` requests means code brute force; one or two means a disposable
inbox.

The origin must stop accepting direct connections: firewall 80/443 to
Cloudflare's published ranges, or put the origin behind a Tunnel. Until then,
`CF-Connecting-IP` is not trustworthy and the per-IP limits can be evaded.

### 4.5 Verify the deployment

```bash
docker compose -f deploy/docker-compose.prod.yml exec -T api printenv ENVIRONMENT
```

Must be `production`. Also verify `TURNSTILE_SECRET_KEY` is non-blank and
`VITE_TURNSTILE_SITE_KEY` was present in the web build. On 19 Nov the site and
secret keys were installed in the server-only `.env`, the front was rebuilt and
the API recreated. A tokenless login/reset now returns `400`, while a real
solved token is accepted.

### 4.6 Origin allowlist (applied 19 Nov)

Cloudflare publishes its ranges at `https://www.cloudflare.com/ips-v4`. The
server now runs:

- `/usr/local/sbin/chmaba-cloudflare-allowlist.sh` builds the `CHMABA_CF` chain
  with `RELATED,ESTABLISHED`, loopback, `127.0.0.0/8`, `172.16.0.0/12` and every
  Cloudflare IPv4 range, then drops the rest.
- `DOCKER-USER` jumps to `CHMABA_CF` for TCP 80/443. Docker-published ports are
  forwarded, so filtering in `DOCKER-USER` is what actually closes the origin.
- `chmaba-cloudflare-allowlist.service` runs at boot after Docker;
  `chmaba-cloudflare-allowlist.timer` refreshes the ranges every six hours and
  falls back to a built-in list if Cloudflare is unreachable.

Verified after applying:

- direct `https://163.245.204.122/api/v1/health` from a non-Cloudflare host:
  connection fails;
- `https://chmaba.com/api/v1/health`: `200`;
- `https://admin.chmaba.com/`: `200`;
- `https://shops.chmaba.com/`: `302` to `/stores`.

This is IPv4-only because the origin has no IPv6 listener. If IPv6 is added,
extend the script with `ips-v6`. The one-off `66.163.112.172` drop was
superseded and removed; the allowlist now rejects every non-Cloudflare source.

## 5. Remaining work

### P0 — before the next signup window

- [x] Deploy the first slice (`843929c`). Production rejects `example.com`
      with `400` and throttles the sixth register attempt with `429`.
- [x] Suspend the probe users, company and store; revoke their sessions.
- [x] **Cloudflare-only origin**: applied 19 Nov. `DOCKER-USER` allows TCP
      80/443 only from Cloudflare's IPv4 ranges (plus loopback and Docker
      networks) and drops the rest. Direct-origin requests now fail while
      Cloudflare serves normally; see §4.6.
- [ ] **Block the attacker at the edge**: add `66.163.112.172` (and the GTHost
      ASN if it persists) to a Cloudflare WAF block rule. The origin allowlist
      stops direct access, but proxied traffic from that address still reaches
      Cloudflare.
- [ ] **Turnstile keys**: create the widget and set
      `TURNSTILE_SECRET_KEY`, `TURNSTILE_SITE_KEY` and
      `VITE_TURNSTILE_SITE_KEY`. Production is still blank today.
- [ ] Rotate duke's password and enable 2FA as a precaution, even though the
      reset did not complete.

### P1 — before the next production signup window

- [x] **Turnstile on**: site and secret keys are server-only; the web and
      admin widgets are baked in, and `admin.chmaba.com` is in the widget's
      hostname list. Tokenless login/reset returns `400`; a real solved token is
      accepted.
- [x] **Bind the verification code to the account**. Register/resend return a
      `verification_id`; `POST /auth/verify-email` sends
      `{verification_id, token}` and the lookup is `id + token_hash`. Production
      rejects a request without the id; a bound id allows five attempts per
      fifteen minutes. Web, admin, Android, iOS, e2e and the API client are
      updated. In dev/test the legacy token-only path remains so the suites can
      exercise it.
- [ ] **Move the limiter to shared storage** (Redis/Postgres) before running
      more than one API worker. `app.services.support.check_rate_limit` is
      in-process today, so limits multiply by worker count.
- [x] **Limit hard by origin**: the 80/443 allowlist is applied and persisted
      (§4.6). `CF-Connecting-IP` is now trustworthy because direct access is
      dropped.
- [ ] **Mandatory TOTP 2FA** for `admin`/`super_admin`, with recovery codes.
      There is no MFA implementation in this repository today.
- [ ] **Log failed sign-ins** (email hash + IP + user-agent, never the password)
      and alert on spikes. Today only successful logins reach
      `platform_activities`.
- [ ] **Auto-expire unverified accounts** (7 days) and add an audited admin
      delete action.
- [ ] **Cap invitations per company/day**; review `accept-by-owner` (owner/team
      manager) and make its temp-password handling explicit.
- [ ] **Email reputation**: replace the static disposable list with a maintained
      check (MX/reputation/disposable API) and risk-score Gmail-style signups
      instead of blocking them outright.

### P2 — monitoring and tests

- [ ] Alert when one IP/domain creates more than N accounts per hour, when
      verification failures spike, when an admin reset is requested, or when an
      admin signs in from a new country/ASN.
- [x] Tests for Turnstile enforcement and verification-code binding.
- [ ] Tests for unverified-account expiry, invitation caps and the production
      `dev_verification_token` guard.
- [ ] Add a production smoke test that asserts
      `ENVIRONMENT=production` and Turnstile configured.

## 6. Acceptance checks for this slice

- A production registration for `*@example.com`, `*@mailinator.com` or
  `*@euploading.com` returns `400`.
- Six registrations from one address in an hour return `429` on the sixth (with
  the production limits; tests set their own).
- Five wrong passwords for one address return `429` on the next attempt; a
  successful sign-in clears the window.
- A suspended user with the correct password gets `403`.
- `X-Real-IP` contains the Cloudflare visitor address in production, and
  `auth_sessions.ip_address` matches it.
- The Admin users list shows "Unverified" for never-verified accounts.

## 7. Residual risks

- A distributed botnet can spread attempts across IPs. Per-account limits and
  Turnstile are the counterweight; shared-state limiting is still required for a
  multi-worker deployment.
- A 6-digit code remains guessable in principle until the binding change lands.
- The static disposable-domain list will age; treat it as a speed bump.
- Per-address login lockout can be abused to lock a known account for fifteen
  minutes. The window is short on purpose; add CAPTCHA or progressive delay
  before lengthening it.
