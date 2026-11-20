# Activation Intelligence — Requirements & Delivery Plan

Status: Proposed
Owners: Product (accountable), Engineering (delivery), Support/Ops (consumers)
Companion: `docs/onboarding-activation-analytics-plan.md` (telemetry schema,
funnel definitions, SDK, privacy). This document is the **requirements and
delivery contract**; the companion is the **data foundation**.

Scope: Build one system that (a) records how every merchant actually uses
Chmaba from landing to first sale, (b) explains where and why they stop, and
(c) uses AI to turn that evidence into ranked, testable product changes — then
proves whether a change worked.

---

## 0. One-paragraph summary

Today we can say *"60% of verified users never create a workspace"* and nothing
more. We will instrument the full journey with server-authoritative milestones
plus click/error/timing context, put a cohort funnel and session timeline in the
admin panel, and add an **AI insight layer** that reads only aggregated and
redacted evidence to produce a weekly, ranked list of friction points with
citations, a draft hypothesis, a proposed flow change, and the experiment that
would prove it. No AI output ships to merchants or to `main` without a human and
a measured result.

---

## 1. Product requirements

### 1.1 Problem statement

A merchant signs up, verifies their email, and then must complete a three-step
wizard, land in a workspace, add a real product, open a shift, and ring up a
sale. We do not know which of those steps loses them, how long each takes, or
what error they saw when they quit. Support sees the survivors, not the
drop-offs. Product decisions are made from anecdotes and a five-stage chart
whose stages are counted with different denominators.

The cost is direct: every merchant who stalls before their first sale is a
workspace that may churn before it ever pays, and every unnecessary step is a
tax on the ones who make it.

### 1.2 Users and jobs to be done

| User | Job | What they need from this system |
|---|---|---|
| Founder / PM | Decide what to fix next | A ranked, evidence-backed list of friction points with expected impact |
| Ops / support lead | Rescue stalled merchants | A list of who is stuck *now*, on which step, and a stage-appropriate message |
| Engineer | Fix the real cause | The failing endpoint, error key, field, route, and a reproducible session timeline |
| Designer | Reduce steps | Where users loop, backtrack, or hunt; which step has no conversion value |
| Platform admin | Keep it trustworthy | Ingest health, privacy controls, cost, and audit of who read what |

### 1.3 Goals

1. One cohort-based funnel from landing to second sale, correct on day one.
2. Sub-step visibility: every wizard step, form, and payment state is measurable.
3. "Why" on the same screen: errors, latency, dwell, dead/rage clicks, survey.
4. A session timeline a non-engineer can read in 20 seconds.
5. AI that produces **cited** findings and **testable** proposals, weekly.
6. A closed loop: proposal → experiment → cohort result → keep or revert.
7. Zero PII or secrets in the analytics store; 90-day raw retention.

### 1.4 Non-goals

- No advertising pixels, cross-site tracking, or data sale.
- No AI autonomously changing product copy, flows, pricing, or code.
- No full session video in phase 1 (replay is optional, phase 7).
- No replacement of the support assistant; this feeds it context.
- No warehouse/OLAP migration until volume proves it necessary.
- No merchant-facing dashboards in phase 1 (internal first).

### 1.5 Success metrics

| Metric | Definition | Baseline | 90-day target |
|---|---|---|---|
| Activation rate | New signups with a paid sale within 7 days | measure in phase 0 | +10 pp |
| Time to first sale | median, signup → first paid order | measure | −40% |
| Verify rate | signups verified within 24 h | measure | +10 pp |
| Setup completion | verified → workspace created | measure | +15 pp |
| First product | workspace → real product within 24 h | measure | +15 pp |
| Step count | median screens from signup to first sale | measure | −20% |
| Insight latency | days from signal to shipped fix | n/a | ≤ 14 |
| AI trust | % of AI findings accepted by a human reviewer | n/a | ≥ 70% |
| Data integrity | funnel reconciled with `PlatformActivity` | n/a | ≥ 99% |

Guardrails (must not regress): p95 of `/workspaces/current` and `/orders`,
client JS error rate, rage-click rate, support tickets per 100 new workspaces,
refund/void rate in new workspaces.

### 1.6 Scope matrix

| Surface | Phase 1 | Later |
|---|---|---|
| `apps/web` merchant app | full: events, clicks, errors, steps | replay (optional) |
| `apps/storefront` | shopper funnel milestones | full click stream if needed |
| `apps/android`, `apps/ios` | milestone events via API | screen-level events |
| `chmabapos_api` | authoritative milestone events | derived scoring jobs |
| `apps/admin` | funnel, timeline, why, AI copilot | experiments, cohort explorer |

---

## 2. Functional requirements

Requirements are numbered and testable. `MUST` = release blocker for the named
phase; `SHOULD` = expected; `MAY` = optional.

### 2.1 Capture (FR-C)

| ID | Requirement | Priority | Phase |
|---|---|---|---|
| FR-C1 | The system MUST accept batched events from an unauthenticated client, with an optional bearer token for identity. | MUST | 1 |
| FR-C2 | It MUST record every meaningful click on merchant routes unsampled, and MUST NOT record input values or secrets. | MUST | 3 |
| FR-C3 | It MUST capture page/route views with dwell, scroll depth, and route keys (no raw usernames or tokens). | MUST | 3 |
| FR-C4 | It MUST capture client errors, failed API calls (endpoint key, status, code), and navigation timing. | MUST | 3 |
| FR-C5 | It MUST capture rage clicks (≥3 in 1 s within 32 px) and dead clicks (no effect in 700 ms). | MUST | 3 |
| FR-C6 | It MUST capture form field focus/blur/validation-failure with field names, never values. | MUST | 3 |
| FR-C7 | It MUST record a heartbeat every 30 s while a funnel step is open, so abandonment is measurable when a tab dies. | MUST | 3 |
| FR-C8 | It MUST queue offline and flush on reconnect, and use `sendBeacon` on unload. | MUST | 3 |
| FR-C9 | It MUST drop events from platform-admin users (`is_internal`). | MUST | 1 |
| FR-C10 | It MUST reject bots and enforce per-session/per-IP rate limits. | MUST | 1 |
| FR-C11 | Server code MUST emit authoritative milestone events for register, verify, login, workspace, plan, product, shift, sale, refund, payment link, invite. | MUST | 1 |
| FR-C12 | Server events MUST commit atomically with the business row, or via an outbox, and MUST never fail the business operation. | MUST | 1 |
| FR-C13 | Every event MUST carry a client-generated id, deduped server-side. | MUST | 1 |
| FR-C14 | The client SDK MUST be ≤ 8 KB gzip, zero dependencies, non-blocking. | MUST | 3 |

### 2.2 Identity (FR-I)

| ID | Requirement | Priority | Phase |
|---|---|---|---|
| FR-I1 | Anonymous pre-signup behaviour MUST be attributable after signup via `anonymous_id` stitching. | MUST | 1 |
| FR-I2 | A session MUST be one identity across route changes, with 30-minute inactivity rotation. | MUST | 1 |
| FR-I3 | `company_id`/`store_id` MUST be server-derived, never trusted from the client. | MUST | 1 |
| FR-I4 | A verification link opened on a different device MUST resolve to the right user. | MUST | 2 |
| FR-I5 | Invited staff MUST NOT count as new-workspace activations; activation is per company, attributed to the owner. | MUST | 2 |
| FR-I6 | Attribution (referrer, `utm_*`) MUST be captured on first landing and persisted for the user. | SHOULD | 3 |

### 2.3 Journey analytics (FR-J)

| ID | Requirement | Priority | Phase |
|---|---|---|---|
| FR-J1 | A cohort funnel MUST show S0–S19 for users created in the window, monotonically non-increasing. | MUST | 2 |
| FR-J2 | Each stage MUST show count, % from previous, % from start, median and p90 time, and stalled count. | MUST | 2 |
| FR-J3 | Any stage MUST be breakable down by vertical, country, currency, plan, locale, device, browser, source. | MUST | 4 |
| FR-J4 | The system MUST list sessions that stopped at a stage, with last route, last action, dwell, and error. | MUST | 4 |
| FR-J5 | A session timeline MUST render page views, step events, clicks, API failures, errors, and idle gaps in order. | MUST | 4 |
| FR-J6 | The system MUST compute a per-stage friction score (§4.3) and rank stages by it. | SHOULD | 4 |
| FR-J7 | The system MUST compute a route transition matrix per cohort to expose loops and backtracking. | SHOULD | 4 |
| FR-J8 | Signup cohorts MUST show stage-reached heatmaps by week, to compare before/after a fix. | MUST | 4 |
| FR-J9 | Old `/admin/funnel` MUST run in parallel until reconciled within 1%, then be deprecated. | MUST | 2 |

### 2.4 Diagnosis (FR-D)

| ID | Requirement | Priority | Phase |
|---|---|---|---|
| FR-D1 | The system MUST aggregate validation failures by form + field + rule. | MUST | 4 |
| FR-D2 | It MUST aggregate API failures by endpoint + status + error code. | MUST | 4 |
| FR-D3 | It MUST expose p50/p95 latency per funnel-critical endpoint. | MUST | 4 |
| FR-D4 | It MUST capture a one-question abandonment survey on idle/back-out, with an optional 280-char reason. | SHOULD | 5 |
| FR-D5 | It MUST classify support conversations into a fixed theme set and join themes to the user's stage. | SHOULD | 5 |
| FR-D6 | Every diagnosis MUST link to at least one example session. | MUST | 4 |

### 2.5 AI insight layer (FR-A)

| ID | Requirement | Priority | Phase |
|---|---|---|---|
| FR-A1 | The system MUST generate a daily/weekly **Friction Digest**: top stages by friction, each with cited evidence. | MUST | 6 |
| FR-A2 | Every AI claim MUST cite event ids, metric keys, or session ids; uncited claims MUST be rejected by a validator. | MUST | 6 |
| FR-A3 | The system MUST generate a **Session Story**: a plain-language cause for a dropped session, with the evidence trail. | MUST | 6 |
| FR-A4 | It MUST cluster survey answers + support themes + dead clicks into named themes with counts and examples. | SHOULD | 6 |
| FR-A5 | It MUST propose **step reductions** (merge/remove/reorder) with an estimated conversion effect and a test design. | SHOULD | 6 |
| FR-A6 | It MUST propose experiments with hypothesis, variant, primary metric, sample size, and guardrails. | SHOULD | 6 |
| FR-A7 | It MUST never send raw PII, names, emails, phones, or free-text customer data to a provider. | MUST | 6 |
| FR-A8 | Every AI run MUST be logged with provider, model, tokens, cost, prompt version, and evidence ids. | MUST | 6 |
| FR-A9 | A human MUST accept, edit, or reject each insight; the decision MUST be stored. | MUST | 6 |
| FR-A10 | AI MUST NOT auto-apply any product change. | MUST | 6 |
| FR-A11 | When the provider fails, the system MUST fall back to deterministic rules and say so. | MUST | 6 |
| FR-A12 | The AI copilot MUST answer "why did activation drop last week?" using only permitted tools/queries. | SHOULD | 7 |
| FR-A13 | Merchant rescue messages MUST reuse the existing stage-aware outreach context, not invent a new one. | SHOULD | 8 |

### 2.6 Operations (FR-O)

| ID | Requirement | Priority | Phase |
|---|---|---|---|
| FR-O1 | Alerts MUST fire on stage conversion WoW change > ±15%, ingest lag > 10 min, reject rate > 5%, setup 5xx > 1%. | SHOULD | 4 |
| FR-O2 | Ingest health MUST be visible in the admin panel (volume, lag, rejects, partitions). | MUST | 4 |
| FR-O3 | CSV export MUST exist for funnels and stage breakouts, with PII excluded. | SHOULD | 4 |
| FR-O4 | Per-user and per-workspace telemetry deletion MUST be possible and audited. | MUST | 1 |
| FR-O5 | Raw retention MUST default to 90 days and rollups to 24 months. | MUST | 1 |

---

## 3. Non-functional requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-1 | Collector availability | 99.9%, and its failure never affects product endpoints |
| NFR-2 | Collector latency | p95 < 150 ms for a 20-event batch |
| NFR-3 | Funnel query | p95 < 400 ms at 30 days / 5M events |
| NFR-4 | Client overhead | < 2 ms/event main thread, < 8 KB gzip, no blocking request |
| NFR-5 | Data freshness | events visible < 60 s; rollups < 24 h |
| NFR-6 | Privacy | zero secrets/PII in store, verified by automated scanner |
| NFR-7 | Security | platform-admin only; every read audited |
| NFR-8 | i18n | admin UI strings via the existing pattern; AI output in English, merchant-facing output in en/km |
| NFR-9 | Cost | telemetry + AI < $150/month at 2,000 MAU |
| NFR-10 | Reversibility | every phase behind a flag/env switch |
| NFR-11 | Accessibility | admin page keyboard navigable, no colour-only encoding |
| NFR-12 | Portability | event/registry contract versioned; provider swappable |

---

## 4. How the intelligence works

### 4.1 The four analytical objects

Everything in the admin and AI layer is derived from exactly four objects.
This is the contract that keeps AI honest.

1. **Stage** — a named point in the canonical funnel with a definition and a
   denominator (§4.3).
2. **Evidence** — any countable fact: an event count, an error key, a p95, a
   survey theme, a session id.
3. **Finding** — one sentence + evidence ids + a confidence + an owner.
4. **Proposal** — a change (copy, step merge, validation, endpoint fix) + a
   hypothesis + a metric + a test design.

AI may only produce Findings and Proposals; it may never produce a Stage
definition or a number that is not computed by a query.

### 4.2 Evidence contract

Every AI input is a JSON object with:

```jsonc
{
  "window": { "start": "2026-11-01", "end": "2026-11-14" },
  "cohort": "signup",
  "stage": {
    "key": "workspace",
    "label": "Workspace created",
    "entered": 412,
    "completed": 248,
    "abandoned": 164,
    "median_dwell_s": 184,
    "p90_dwell_s": 1204,
    "back_rate": 0.11,
    "friction_score": 0.72
  },
  "errors": [{ "key": "validation.currency_unsupported", "count": 31 }],
  "api_failures": [{ "endpoint": "POST /workspaces/setup", "status": 500, "count": 12 }],
  "dead_clicks": [{ "element_key": "onboarding.plan.continue", "count": 27 }],
  "survey_themes": [{ "theme": "plan too expensive", "count": 9 }],
  "support_themes": [{ "theme": "billing", "count": 14 }],
  "example_sessions": ["sess_…", "sess_…"],
  "baseline": { "previous_window_conversion": 0.58 }
}
```

No names, emails, phones, addresses, order amounts, or free text. Company and
user ids are pseudonymised (`company_7f3a`) before the prompt. The full contract
is validated by a Pydantic model; a prompt built from anything else is rejected.

### 4.3 Friction score (deterministic, not AI)

```
friction(stage) =
    0.35 * abandon_rate
  + 0.20 * min(p90_dwell_s / 900, 1)
  + 0.15 * error_rate
  + 0.10 * back_rate
  + 0.10 * dead_click_rate
  + 0.10 * support_theme_rate
```

Weights live in config, are versioned, and are shown in the UI. AI ranks and
explains; it does not invent the score. This is the single most important design
choice in the AI section: **the numbers are deterministic, the narrative is
generated.**

### 4.4 The six AI capabilities

#### A. Friction Digest (daily)

Input: evidence for all stages, previous window, open proposals.
Output:

```jsonc
{
  "headline": "Workspace setup lost 40% of verified users; the plan step is the sink",
  "findings": [
    {
      "stage": "plan_confirmed",
      "severity": "high",
      "claim": "31 users saw 'currency is not supported' after choosing a paid plan",
      "evidence": ["error:validation.currency_unsupported", "sessions:3"],
      "confidence": 0.82
    }
  ],
  "recommended_focus": "plan_confirmed",
  "do_nothing": ["pos", "orders"]
}
```

Validator rejects any finding without a resolvable evidence id, any number not
present in the input, and any claim about a stage not in the input.

#### B. Session Story (on demand)

Input: one session timeline (events, errors, dwell, survey answer), pseudonymised.
Output: 3–6 sentences: what they tried, where it broke, most likely cause, and
what to check. Used in the admin drawer so an engineer does not read 200 rows.

#### C. Theme Clustering (weekly)

Input: survey free-text (consented), classified support messages, dead-click
labels.
Output: 5–10 named themes with counts, representative (redacted) quotes, and the
stage they cluster on. Deterministic fallback: keyword buckets.

#### D. Step Reducer

Input: transition matrix, per-step conversion, per-step dwell, downstream
success conditional on step.
Output: a ranked list of steps to merge/remove/reorder, each with:

- the step's marginal contribution (`conversion with step` vs `without`, where
  computable; otherwise a stated assumption),
- the risk,
- the experiment that would settle it.

This directly answers "what can we reduce to make them sell faster?" without
guessing. A step is only proposed for removal if its removal plausibly preserves
downstream conversion.

#### E. Experiment Designer

Input: a chosen finding + baseline metric + traffic estimate.
Output: hypothesis, variant description, primary metric, guardrails, minimum
sample, expected duration, and the exact funnel query that will judge it.
The system then creates a draft experiment record (no traffic split until a
human enables it).

#### F. Merchant Rescue (reuses `support_outreach.py`)

Input: a stalled merchant's real stage (already computed by
`build_context`/`_classify`), plus the friction evidence for the step they are
stuck on.
Output: a subject + short message + the exact next step, in en/km, reviewed by
ops before sending. No new context pipeline: this extends
`support_outreach.build_context` with the analytics stage.

### 4.5 Prompt and output contracts

- All AI calls go through `app/services/ai.py::complete_chat` (provider-agnostic,
  already supports OpenAI/DeepSeek/Anthropic, already records usage).
- Each capability has a versioned system prompt (`activation_ai_v1`, `_v2`…)
  stored in code, never in the DB, so diffs are reviewable.
- Output MUST be strict JSON, parsed and validated; on parse failure, one retry
  with a repair instruction, then deterministic fallback.
- `temperature` 0.2–0.3; `max_tokens` 900 (digest) / 500 (session) / 700 (theme).
- Every run stores: prompt version, provider, model, tokens, cost, latency,
  input hash, output, validator result.

### 4.6 Evaluation (how we know the AI is useful, not just plausible)

Build a golden set of **40 items** before enabling the digest in production:

| Set | Size | Label |
|---|---|---|
| Sessions with a known cause | 15 | hand-written expected cause |
| Survey clusters | 10 | expected themes |
| Engineered regressions | 10 | e.g. force a 500 on `/workspaces/setup`; digest must surface it |
| No-signal cases | 5 | digest must say "nothing significant", not invent |

Metrics:

- **Grounding**: 100% of claims cite a valid evidence id (hard gate; validator).
- **Agreement**: ≥ 80% of findings match a human reviewer's top-3 friction list.
- **Specificity**: human 1–5 score ≥ 4 ("would I act on this?").
- **No-signal discipline**: 0 invented findings on the 5 quiet cases.
- **PII leak**: 0 (scanner over prompt + output).

Run the golden set on every prompt change in CI (recorded fixtures, no live
provider call in tests).

### 4.7 Cost model

At 2,000 MAU, 30 days:

| Capability | Runs | Tokens/run | Monthly tokens |
|---|---|---|---|
| Digest | 30 | ~6k in / 1k out | ~210k |
| Session Story | 50/day (on demand, capped) | ~2k | ~3M |
| Themes | 4 | ~8k | ~32k |
| Step/Experiment | 20 | ~4k | ~80k |

At `gpt-4o-mini`/DeepSeek prices this is roughly **$3–15/month**; with Claude
Sonnet, roughly **$40–90/month**. Cap per-company and platform spend in config;
record every call. The cost is not the risk; bad findings are.

### 4.8 AI guardrails

1. Evidence-only prompts; validator rejects unsupported claims.
2. Human accept/reject/edit stored with reason.
3. No auto-apply, no auto-send, no code generation into the repo.
4. Provider fallback to deterministic rules, labelled "rules-based".
5. Redaction pipeline runs before the prompt and is unit-tested with
   canary strings (fake email/phone/token must never appear in the payload).
6. Provider choice respects data residency; prefer a no-training API tier.
7. Kill switch: `ACTIVATION_AI_ENABLED=false` disables all generation, UI shows
   the deterministic report instead.

---

## 5. Data model additions (AI layer)

```sql
CREATE TABLE ai_insights (
  id             uuid PRIMARY KEY,
  created_at     timestamptz NOT NULL DEFAULT now(),
  kind           text NOT NULL,            -- digest | session_story | theme | step | experiment
  window_start   timestamptz,
  window_end     timestamptz,
  stage_key      text,
  title          text NOT NULL,
  summary        text NOT NULL,
  severity       text NOT NULL,            -- low | medium | high
  confidence     numeric(3,2),
  evidence       jsonb NOT NULL,           -- [{type, id, metric, value}]
  payload        jsonb NOT NULL,           -- structured output
  prompt_version text NOT NULL,
  provider       text, model text,
  input_hash     text NOT NULL,
  validator      text NOT NULL,            -- passed | repaired | fallback
  decision       text,                     -- accepted | rejected | edited | null
  decided_by     uuid REFERENCES users(id),
  decided_at     timestamptz,
  decision_note  text
);

CREATE TABLE ai_runs (
  id            uuid PRIMARY KEY,
  created_at    timestamptz NOT NULL DEFAULT now(),
  insight_id    uuid REFERENCES ai_insights(id) ON DELETE SET NULL,
  prompt_version text NOT NULL,
  provider      text, model text,
  prompt_tokens int, completion_tokens int, cost_usd numeric(10,4),
  latency_ms    int,
  outcome       text NOT NULL              -- ok | parse_error | provider_error | fallback
);

CREATE TABLE activation_experiments (
  id             uuid PRIMARY KEY,
  created_at     timestamptz NOT NULL DEFAULT now(),
  hypothesis     text NOT NULL,
  stage_key      text NOT NULL,
  primary_metric text NOT NULL,
  guardrails     jsonb NOT NULL,
  variant        jsonb NOT NULL,
  status         text NOT NULL DEFAULT 'draft',  -- draft|running|stopped|shipped|reverted
  started_at     timestamptz, ended_at timestamptz,
  result         jsonb,
  insight_id     uuid REFERENCES ai_insights(id) ON DELETE SET NULL
);

CREATE TABLE activation_annotations (
  id         uuid PRIMARY KEY,
  created_at timestamptz NOT NULL DEFAULT now(),
  scope      text NOT NULL,        -- deploy | marketing | incident | pricing
  starts_at  timestamptz NOT NULL,
  ends_at    timestamptz,
  label      text NOT NULL,
  note       text,
  created_by uuid REFERENCES users(id)
);
```

Annotations matter: without them, the AI will "explain" a conversion drop that
was actually a deploy or a campaign. The digest must always check for
overlapping annotations and mention them first.

---

## 6. Delivery plan — activities and deliverables

Estimates are engineer-days for one engineer. Phases 1 and 3 can run in
parallel; 6 depends on 2 and 4.

### Phase 0 — Requirements freeze and baseline (3–4 d)

| ID | Activity | Deliverable | Acceptance |
|---|---|---|---|
| 0.1 | Agree the 25 questions and the S0–S19 funnel | Signed funnel table in the companion doc | Product + Eng sign-off in the PR |
| 0.2 | Define event registry v1 (~70 events) | `analytics_registry.py` skeleton + taxonomy doc | Every event has owner, props, sample, PII class |
| 0.3 | Run cohort baseline SQL | `docs/activation-baseline.md` with the 5-stage cohort numbers | Numbers reproducible from `main` |
| 0.4 | Privacy review of the plan | Updated privacy-policy paragraph + retention table | Reviewed by whoever owns compliance |
| 0.5 | Instrumentation budget | Event volume + cost estimate | Fits NFR-9 |

Gate: no code until 0.1–0.3 are merged.

### Phase 1 — Telemetry foundation (5–7 d)

| ID | Activity | Deliverable | Acceptance |
|---|---|---|---|
| 1.1 | Models + migration + partitions | `AnalyticsSession`, `AnalyticsEvent`, `AnalyticsDailyRollup`; single Alembic head | Migration up/down on a copy of prod |
| 1.2 | Collector endpoint | `POST /telemetry/events` with limits, dedupe, sanitizer | Contract tests; PII canary suite passes |
| 1.3 | Identity resolution | anonymous → user → company stitching | Test: verify link on another device joins correctly |
| 1.4 | Server `emit()` + hooks | Events for register/verify/login/workspace/plan/product/shift/order/refund/link/invite | One test per hook; emit never breaks the caller |
| 1.5 | Partition + rollup workers | Scheduled jobs + health metrics | Rollup idempotent; late events re-rolled |
| 1.6 | Deletion + retention | Purge by user/company; 90-day partition drop | Test deletes both event and session rows |
| 1.7 | Ingest health endpoint | `/admin/journeys/health` | Shows volume, lag, rejects, partition list |

Gate: can replay a synthetic signup→sale and see every milestone.

### Phase 2 — Cohort funnel API (3–4 d)

| ID | Activity | Deliverable | Acceptance |
|---|---|---|---|
| 2.1 | Cohort funnel query | `GET /admin/journeys/funnel` | Monotonic stages; invited staff excluded |
| 2.2 | Per-stage timing | median/p90 dwell + stalled | Matches manual SQL on 30 days |
| 2.3 | Parallel run vs old funnel | Reconciliation report | Difference ≤ 1% or explained |
| 2.4 | Stage breakdown contract | breakdown by dimension | Covers vertical/country/plan/device/locale |
| 2.5 | Deprecation plan | Old `/admin/funnel` marked legacy | Removal PR after 2 green weeks |

Gate: funnel numbers trusted; old chart still available.

### Phase 3 — Web SDK and step instrumentation (6–8 d)

| ID | Activity | Deliverable | Acceptance |
|---|---|---|---|
| 3.1 | SDK core | `lib/analytics.js` (init/identify/page/track/step/flush) | Unit tests; size ≤ 8 KB |
| 3.2 | Batching/offline/beacon | Queue + retry + `sendBeacon` | Survives reload and offline→online |
| 3.3 | Autocapture + rage/dead | Global listener + heuristics | Thresholds configurable; no value capture |
| 3.4 | Route instrumentation | `App.jsx` page events with route keys | Setup routes map to `setup.company` etc. |
| 3.5 | Onboarding steps | step view/complete/back/abandon, plan view/select, submit error | E2E emits the exact sequence |
| 3.6 | Auth/verification | form start/submit/error, code submit/resend, device switch | No token in any event |
| 3.7 | Product create | open, field edits, validation, save, abandon | Field names only, never values |
| 3.8 | KHQR | open, paste, verify error reason, test scan | Reason codes normalized |
| 3.9 | First sale | cart start, checkout, method, paid/failed | Correlates with server `order.paid` |
| 3.10 | Coach/help/support | shown/show-me/dismiss/complete, article, chat | `funnel_step` attached |
| 3.11 | `data-track` pass | Stable keys on funnel controls | Key list documented |
| 3.12 | Privacy tests | Canary suite in Playwright | Password/token/phone never present |

Gate: a real signup→sale produces a complete, readable timeline.

### Phase 4 — Journeys admin page (6–8 d)

| ID | Activity | Deliverable | Acceptance |
|---|---|---|---|
| 4.1 | Stage table | counts, %, timing, stalled | Matches API in all ranges |
| 4.2 | Drilldown | breakdown bars + why panel | Every bar click filters the list |
| 4.3 | Dropped-session list | last route/action/dwell/error | Links to timeline |
| 4.4 | Session timeline | ordered events, gaps, errors | Loads < 500 ms for 500 events |
| 4.5 | Cohort heatmap | week × stage | Compares two cohorts |
| 4.6 | Transition matrix | route loops + backtracking | Top loops listed |
| 4.7 | Friction score | ranked stages + weights shown | Deterministic; versioned weights |
| 4.8 | Health + export + alerts | ingest health, CSV, daily digest | Alert fires on synthetic anomaly |
| 4.9 | AdminPageHeader + nav | page wired per `AGENTS.md` | No hand-rolled header |

Gate: all 25 questions answerable without SQL.

### Phase 5 — Qualitative layer (4–5 d)

| ID | Activity | Deliverable | Acceptance |
|---|---|---|---|
| 5.1 | Abandon survey | one-question prompt at idle/back | Non-blocking; dismissible; stored |
| 5.2 | Survey storage + API | answers with step + locale | Free text capped, opt-in |
| 5.3 | Support theme classifier | nightly labels + confidence | Fixed taxonomy; fallback keywords |
| 5.4 | Theme → stage join | why panel shows themes | Example sessions linkable |
| 5.5 | Ops review flow | accept/reject a theme | Stored with reason |

Gate: "why" panel contains at least one human-readable reason per top stage.

### Phase 6 — AI insight engine (7–10 d)

| ID | Activity | Deliverable | Acceptance |
|---|---|---|---|
| 6.1 | AI tables + migration | `ai_insights`, `ai_runs` | Single head; indexes |
| 6.2 | Evidence builder | Pydantic model + SQL for stage evidence | Redaction canary suite passes |
| 6.3 | Prompt v1: digest | system prompt + JSON schema + parser | Golden set runnable offline |
| 6.4 | Validator | citation + number + stage checks | Rejects 100% of injected fake claims |
| 6.5 | Session Story | on-demand endpoint + drawer | ≤ 6 sentences, cited |
| 6.6 | Theme clustering | weekly job + fallback | Matches ≥ 80% of golden themes |
| 6.7 | Step reducer + experiment designer | proposals with test design | Each proposal names a metric + sample |
| 6.8 | Usage + cost + kill switch | `ai_runs`, spend cap, env flag | Exceeding cap degrades gracefully |
| 6.9 | Golden-set harness | 40 fixtures + CI job | Runs without network |
| 6.10 | Human decision loop | accept/reject/edit + note | Every insight has an owner |

Gate: 2 weeks of digests, ≥ 70% accepted, 0 uncited claims, 0 PII leaks.

### Phase 7 — AI copilot in admin (4–6 d)

| ID | Activity | Deliverable | Acceptance |
|---|---|---|---|
| 7.1 | Tool-constrained Q&A | "why did X drop?" over approved queries | Only allow-listed tools; citations required |
| 7.2 | Query allowlist | funnel, stage, why, sessions, experiments | No free SQL, no PII |
| 7.3 | Conversation memory | thread per admin, 30 days | Deletable |
| 7.4 | UI | copilot panel on Journeys page | Streaming, cancel, copy evidence |
| 7.5 | Audit | every question + tool call logged | Visible in `AuditLog` |

Gate: answers a question in < 15 s with ≥ 1 citation, refuses out-of-scope.

### Phase 8 — Merchant rescue + experiments (5–7 d)

| ID | Activity | Deliverable | Acceptance |
|---|---|---|---|
| 8.1 | Stalled-merchant queue | "stuck now" list by stage + friction | Filters by age, plan, vertical |
| 8.2 | Rescue draft | reuse `support_outreach`, add analytics stage | en/km, ops edits before send |
| 8.3 | Experiment record | draft → running → result | No traffic split until enabled |
| 8.4 | Result report | cohort before/after + guardrails | Auto-generated from funnel query |
| 8.5 | Annotation calendar | deploys/campaigns/incidents | Digest checks overlaps first |

Gate: one full loop: finding → fix → measured result, documented.

### Phase 9 — Hardening and GA (4–5 d)

| ID | Activity | Deliverable | Acceptance |
|---|---|---|---|
| 9.1 | Load test | 10× expected volume | Collector p95 < 150 ms |
| 9.2 | Failure drills | provider down, DB slow, queue full | Product unaffected; UI degrades |
| 9.3 | Runbook | on-call steps, kill switches, retention job | Reviewed by ops |
| 9.4 | Privacy re-audit | scanner + manual review | 0 findings |
| 9.5 | Documentation | taxonomy, metric dictionary, AI eval results | Linked from `docs/` |
| 9.6 | Training | 45-min session for PM/ops/eng | Recording + cheat sheet |

### Total and sequencing

| Phase | Days | Depends on |
|---|---|---|
| 0 | 3–4 | — |
| 1 | 5–7 | 0 |
| 2 | 3–4 | 1 |
| 3 | 6–8 | 1 |
| 4 | 6–8 | 2, 3 |
| 5 | 4–5 | 3 |
| 6 | 7–10 | 2, 4 |
| 7 | 4–6 | 6 |
| 8 | 5–7 | 6, 5 |
| 9 | 4–5 | all |

Critical path: 0 → 1 → 3 → 4 → 6 → 8 → 9 ≈ **40–52 engineer-days**
(~9–11 weeks for one engineer, ~6–7 weeks with two).

First useful artifact: cohort funnel on day ~8. First AI digest on day ~30.
Full closed loop on day ~55.

---

## 7. Roles

| Activity | Accountable | Consulted |
|---|---|---|
| Funnel definition | Product | Eng, Ops |
| Telemetry schema/privacy | Eng lead | Compliance |
| SDK + instrumentation | Web eng | Design |
| Admin UX | Product + Design | Eng |
| AI prompts/eval | Eng (AI) | Product |
| Weekly review | Product | Ops, Eng |
| Rescue outreach | Ops | Product |
| Incident/kill switch | Eng on-call | — |

---

## 8. Operating rhythm (the part that makes it useful)

- **Daily (async, 5 min):** read the AI digest; confirm or reject findings.
  A finding with no decision is a bug in the process.
- **Weekly (30 min):** activation review. One stage, three session stories,
  one survey theme, one proposal. Output: one experiment or one fix.
- **Bi-weekly:** cohort heatmap review; retire a metric nobody used.
- **Monthly:** privacy/retention audit, AI golden-set refresh, cost review.

Definition of a good week: one shipped change with a cohort chart, not one more
dashboard.

---

## 9. Test strategy

| Layer | Tests |
|---|---|
| Schema | migration up/down, partition creation, single Alembic head |
| Collector | valid/invalid batch, size limits, dedupe, bot reject, rate limit, PII canary |
| Identity | anonymous→user stitch, cross-device verify, invited staff exclusion, tenant isolation |
| Funnel | cohort monotonicity, window bounds, timezone edges, reconciliation vs `PlatformActivity` |
| SDK | batching, sampling, offline, sanitizer, size budget (`node --test`) |
| Web e2e | onboarding sequence emits exact events; no token/password in payload (Playwright) |
| Admin | routing, header component, drilldown contract, empty states |
| AI | golden set (grounding, agreement, specificity, no-signal), validator rejects injections, fallback on provider error |
| Security | cross-tenant event injection, admin-only reads, deletion |
| Load | 10× volume, collector and funnel |

CI: the existing nine jobs must stay green. Add the SDK tests to `web`, the
collector/funnel/AI tests to `api`, the admin routing test to `admin`, and one
Playwright spec to `e2e`. Regenerate `openapi.json` and `packages/api-client`
for every new endpoint.

---

## 10. Rollout

1. **Shadow:** collector + server events only, no UI. Compare with
   `PlatformActivity` for a week.
2. **Read-only:** admin funnel + timeline for the platform team. Keep the old
   funnel visible.
3. **AI shadow:** digests generated but hidden; reviewers compare against their
   own list. Only after 2 weeks and the golden set pass does it appear.
4. **Enabled:** AI digest in the daily ops flow; rescue queue live.
5. **Experiments:** first A/B or sequential test on the top friction stage.
6. **Deprecate** the old `/admin/funnel` once reconciled for 2 weeks.

Rollback: `ACTIVATION_AI_ENABLED`, `ANALYTICS_COLLECTOR_ENABLED`,
`ANALYTICS_SDK_ENABLED`; each degrades to the current behaviour, no data loss.

---

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Too much data, no decisions | High | High | Question-driven scope, weekly ritual, delete unused charts |
| Funnel numbers disagree with the ledger | Medium | High | Server-authoritative stages + parallel run |
| AI produces plausible nonsense | High | High | Evidence validator, golden set, human decision loop |
| AI sends PII to a provider | Low | Critical | Redaction before prompt + canary tests + provider review |
| Client SDK slows the POS | Medium | High | Size/perf budget, idle init, failure isolation |
| Ad blockers / offline lose events | Medium | Medium | Server milestones + offline queue + beacon |
| Postgres pressure | Low | Medium | Batch, partitions, 90-day raw, sampling storefront |
| Scope creep into ads/attribution | Medium | Medium | Non-goals are explicit |
| Team bandwidth vs 9-job CI | Medium | Medium | Phases independently shippable |
| "Surveillance" perception from merchants | Low | High | Disclosure, no performance scoring, per-workspace deletion |

---

## 12. Decisions needed before Phase 1

1. **AI provider:** OpenAI / DeepSeek / Claude (the panel already supports all
   three). Cost vs quality vs data residency.
2. **Replay:** none / PostHog Cloud / self-hosted / rrweb. Affects phase 7.
3. **Consent posture:** disclose-only (recommended) vs opt-in.
4. **Retention:** 90 d raw / 24 mo rollups (recommended).
5. **Mobile scope:** milestones only (recommended).
6. **Experiment capability:** build a flag system, or run sequential
   before/after tests only? (Sequential is enough for phase 8.)
7. **Owner of the weekly review.**

---

## 13. Definition of done

**Per phase:** merged PR, green CI, tests listed in §9, doc updated, feature
flag default set, and a one-paragraph "what changed for the user" note.

**Whole programme:**

- Every one of the 25 questions is answerable in the admin UI, with a timestamp
  and a session example.
- Funnel reconciles with `PlatformActivity` ≥ 99%.
- The AI digest has run for 4 consecutive weeks with ≥ 70% accepted findings,
  0 uncited claims, 0 PII leaks.
- At least 3 shipped changes have a before/after cohort chart.
- Activation rate and time-to-first-sale have moved in the intended direction,
  or the programme has documented why not and what it learned.

---

## 14. Appendix

### A. Example digest output (real shape, illustrative content)

```json
{
  "headline": "Plan selection is the biggest sink: 40% of verified users stop there",
  "findings": [
    {
      "stage": "plan_confirmed",
      "severity": "high",
      "claim": "The paid-plan path fails after selection: 12 setup calls returned 500 and 31 returned currency validation errors.",
      "evidence": ["api:POST /workspaces/setup:500:12", "error:validation.currency_unsupported:31"],
      "confidence": 0.86
    },
    {
      "stage": "email_verified",
      "severity": "medium",
      "claim": "Users who verify on a second device take 3.2x longer to log in; 8 sessions show a return to the login screen.",
      "evidence": ["metric:verify_to_login_p90:3.2x", "sessions:8"],
      "confidence": 0.71
    }
  ],
  "recommended_focus": "plan_confirmed",
  "do_nothing": ["pos", "orders"],
  "annotations": ["deploy 2026-11-12 may explain 3 sessions"]
}
```

### B. Example step-reducer proposal

```json
{
  "step": "onboarding.questions",
  "proposal": "merge",
  "rationale": "Only 12% change any answer; 61% accept defaults. Removing it saves 9 s median and 1 screen.",
  "evidence": ["metric:questions_default_accept_rate:0.61", "metric:step_marginal_conversion:0.004"],
  "risk": "Plan recommendation gets less accurate for multi-store merchants",
  "experiment": {
    "hypothesis": "Merging questions into plan selection does not reduce workspace creation",
    "primary_metric": "verified_to_workspace",
    "guardrails": ["plan_mix", "support_tickets_per_100_workspaces"],
    "sample": "n≈1,200 per arm or 3 weeks sequential",
    "judge_query": "GET /admin/journeys/funnel?cohort=signup&stage=workspace"
  }
}
```

### C. Prompt skeleton (digest)

```text
You are a product analyst for Chmaba, a POS for small retailers in Cambodia.
You receive ONLY aggregated evidence. Rules:
- Every claim must cite at least one evidence id that appears in the input.
- Never state a number that is not in the input. Never invent a stage.
- If the evidence does not support a finding, say "nothing significant".
- Prefer findings that name a concrete screen, field, endpoint, or error.
- Return strict JSON matching the provided schema. No prose outside JSON.
```

### D. Metric dictionary (minimum)

`signup_started`, `signup_submitted`, `account_created`, `email_verified`,
`first_login`, `setup_opened`, `company_details_completed`,
`questions_completed`, `plan_confirmed`, `workspace_created`,
`workspace_loaded`, `first_product_added`, `shift_opened`, `cart_started`,
`checkout_opened`, `first_sale`, `second_sale_7d`, `friction_score(stage)`,
`verify_to_login_p90`, `step_marginal_conversion`, `dead_click_rate`,
`rage_click_rate`, `api_error_rate(endpoint)`, `ai_accept_rate`.

### E. What "reduce steps" means operationally

A step is a candidate for removal only when all three hold:

1. Its marginal conversion (downstream success with the step vs without, where
   computable) is below 1 percentage point.
2. Most users accept its defaults (≥ 60%) or it can be inferred server-side.
3. Removing it does not degrade a guardrail (plan mix, support load, refund
   rate) in a sequential or split test.

Otherwise it is a candidate for **merging** or **moving later**, not deletion.
This rule is what stops "reduce steps" from becoming "remove the thing that
protects the merchant from a bad decision".
