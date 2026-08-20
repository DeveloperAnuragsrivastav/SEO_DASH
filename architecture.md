# EZ Rankings SEO Dashboard — Architecture

Status: Ready to build Phase 1 · Scope: Internal use only, EZ Rankings' own
direct clients. White-label/reseller is not designed for at all right now —
see §16. This is the only design document for this project — `tracking.md`
is the only other file, and it's for build-progress tracking, not design
decisions.

---

## 1. Problem

EZ Rankings manages SEO for multiple clients and currently builds monthly
performance reports by hand in Excel. This system automates the data
collection and report assembly. A human still reviews every report before a
client sees it — this system removes the manual pulling and
spreadsheet-building underneath that judgment, not the judgment itself.

---

## 2. Tech stack

- **Backend:** Python 3.x, FastAPI
- **Database:** Postgres, hosted on Supabase — used as managed Postgres (no
  Supabase Auth, no Supabase client SDK dependency in the backend)
- **Frontend:** React
- **Queue / scheduled jobs:** Celery + Redis, for the one recurring job this
  system has (§5)
- **App hosting:** a standard Python-hosting platform alongside Supabase
  (Railway/Render or equivalent) — normal CI/CD, persistent worker processes,
  and Redis are all natively available here, unlike the shared-hosting
  constraint an earlier draft of this document had to work around
- **Data sources:** Google service accounts (GSC, GA4, GBP — §7), DataForSEO
  API (rankings, AI-visibility, keyword research — §4, §6, §8)

---

## 3. Data source strategy

| Category | Sources | Cost | How it's collected |
|---|---|---|---|
| Free, service-account connected | Google Search Console, GA4, Google Business Profile (performance metrics) | ₹0 | Shared service-account pattern (§7), pulled on report-generation click |
| Paid, via DataForSEO | Rank tracking, AI-visibility, keyword research | Usage-based | Rankings need a recurring job (§5); AI-visibility and keyword research are click-triggered |
| Manual entry — always available, for every category above | Anything not connected yet, broken, or not set up for a client | ₹0, staff time | Form or CSV upload (§9) — not limited to the paid sources |

**Every data category has a manual fallback, including the free ones.** GSC,
GA4, and GBP are not assumed to always be connectable. The report pipeline
(§10) reads from whichever source actually has data for a given
client-month: connected-API data if present, manual entry if not.

---

## 4. DataForSEO scope — strictly what's verified available

This project uses exactly what was researched and confirmed, not what the
FoodBazaar prototype's mock UI implied (that prototype was modeled loosely on
Mangools/Semrush, not on DataForSEO's actual endpoints).

| Prototype UI element | What it needs | DataForSEO reality |
|---|---|---|
| Keyword rankings, position bands, 12-month track | Daily position per keyword | **Google Organic SERP API** — the core rankings pipeline (§5) |
| "AI Overview appearances (of N tracked prompts)" | Whether Google's AI Overview SERP feature shows the brand | **Not a separate call** — the same SERP request used for rankings sets `load_async_ai_overview: true` (small additional cost). Bundled into §5, not a separate source. |
| "Mentions by answer engine" (ChatGPT, Claude, Gemini, Perplexity) | Prompt the brand, check if/how it's mentioned | **LLM Responses API** — confirmed across all four platforms (§6) |
| "Traffic from AI platforms" (ChatGPT, Copilot, Perplexity, Gemini referrals) | Real site visits referred by an AI platform | **Not DataForSEO — this is GA4** (session source/medium filtered to AI-referrer domains). Copilot appears here because it's passive traffic-tracking, not active prompt-testing. |
| "Cited pages" | Which client pages get referenced in AI answers | Derived from the LLM Responses output, part of the custom analysis (§6) |

**Rule:** if a future UI element implies a DataForSEO capability not
explicitly verified here, treat it as unverified — check before building.

---

## 5. Rankings — the one recurring scheduled job

Rank tracking is the one thing in this system with no memory of its own past —
the SERP API returns a position *at the moment you call it*. A trend or a
12-month sparkline needs positions captured on a schedule, not reconstructed
after the fact. Everything else in this system is triggered by a person
clicking something; this is the one exception.

```
Celery beat (nightly) → for each client with an active DataForSEO connection
  → batch keywords into task_post calls (Standard method, never Live — 3x
  cheaper, meant for batch) → include load_async_ai_overview (§4) → tag each
  task "{client_id}:{keyword_id}:{date}" → postback_url to a FastAPI webhook
  route → save task_id to provider_tasks immediately (crash recovery),
  linked to this batch's sync_runs row via sync_run_id

DataForSEO processes async → posts to the webhook → match by tag →
  upsert `rankings` (source='api') → mark provider_tasks completed
```

**Reconciliation job — closes the loop, added after this gap surfaced
during implementation.** A submission-time `sync_runs` row starts as
`status='partial'` (tasks submitted, not yet all resolved). Waiting for "the
last webhook" to mark it `success` is not reliable — if DataForSEO ever
drops a single webhook delivery, that row stays `partial` forever with
nothing ever checking it again.

Instead: a separate periodic job (hourly is reasonable — document whatever
interval is chosen and why) reconciles every `sync_runs` row still in
`partial`:
- If every `provider_tasks` row linked to it (via `sync_run_id`) is
  `completed`, mark the `sync_runs` row `success`.
- If any linked task has been `pending` past a staleness threshold (document
  the chosen value against DataForSEO's own Standard-method turnaround
  guidance, not an arbitrary guess), mark that specific task `failed`, and
  once all tasks are resolved mark the `sync_runs` row `partial` (some
  succeeded) or `failed` (none did) — never leave a row nothing will ever
  look at again.
- A stale/failed task past the threshold triggers the same alert channel as
  any other connection failure (§13) — a silently-dropped webhook should be
  just as visible as an outright API failure, not quieter.

No connection → manual CSV upload or a per-keyword entry form (§9) — same
`rankings` table, `source='manual'`.

---

## 6. AI-visibility

**LLM Responses API** — prompt ChatGPT, Claude, Gemini, and Perplexity
directly, run custom analysis (Groq) on the responses to extract mention
count and cited pages. No minimum commitment, covers all four platforms.

Needs a **tracked-prompts list per client** — `ai_prompts`, analogous to
`keywords` for rankings — because "18 of 25 tracked prompts" is a discrete
list, not an aggregate.

**Manual fallback, same shape as rankings:** no connection → staff enters
mention data via a per-platform form. Same `ai_mentions` table,
`source='manual'`.

**Narrative auto-draft:** `report_months.narrative` starts as an
LLM-generated draft (same Groq pattern) summarizing computed KPIs and deltas,
which staff edits before publishing.

---

## 7. Authentication — Google service accounts, not OAuth

GSC, GA4, and GBP scopes are Google-classified as sensitive/restricted. A
standard OAuth flow would require **Google's formal app verification** before
more than 100 accounts could grant access, and every client would see an
"Unverified app" warning during consent until then — verification needs a
security review, branding/domain verification, and for restricted scopes a
video demonstration and **annual re-verification**. (Confirmed against
Google's developer documentation.)

**Service accounts avoid this entirely** — no OAuth consent screen at all. A
client adds our service account's email as a user in their own GSC/GA4/GBP
admin settings, the same motion as adding a team member.

**Two problems this reintroduces — both handled, not just accepted:**

1. **No automatic confirmation.** Mitigation: a "Verify connection" action —
   a real, lightweight test API call against the client's specific
   `property_id` — staff triggers it after asking the client to grant access,
   gets an immediate yes/no.
2. **One shared identity across every client.** A leaked key exposes every
   client at once. Mitigation: envelope encryption (§14), plus its own
   rotation policy given the larger blast radius versus any other credential
   in this system.

**"Which data belongs to which client":** every query is scoped by the
specific `property_id` on that client's `connections` row — never a bulk
"fetch everything visible" call. A periodic check re-verifies each connected
`property_id` is still accessible, so a silently-revoked grant surfaces as
`connections.status = 'error'` instead of silently stale data.

---

## 8. Keyword research

DataForSEO's Keyword Data API, used on-demand when staff chooses keywords for
a client — not part of any recurring job or the report pipeline. Sets
`keywords.search_volume` once, when a keyword is added.

---

## 9. Manual entry — the mechanism, for every source

| Category | Automated source | Manual fallback |
|---|---|---|
| Rankings | DataForSEO SERP API (§5) | CSV upload or per-keyword form |
| AI-visibility | DataForSEO LLM Responses (§6) | Per-platform entry form |
| Search performance | GSC via service account | Manual entry form |
| Analytics | GA4 via service account | Manual entry form |
| Local presence | GBP via service account | Manual entry form |
| Backlinks, content activity, screenshots | — (always manual) | Same as always |

Every row in `rankings`, `metrics`, and `ai_mentions` carries a `source`
(`'api'` or `'manual'`) — the report pipeline reads whatever exists, doesn't
branch on which. A provenance badge in the UI (§15) makes the difference
visible to a reader, not a code path.

---

## 10. Report generation flow

```
Staff clicks "Generate Report" for a client, any day of the month
        │
        ├─→ GSC / GA4 / GBP: if connected, pull live (full previous-month
        │   range, using that connection's property_tz — §14). If not
        │   connected, read manually-entered data for the month.
        │
        ├─→ Rankings: READ from `rankings` — collected nightly, or manually
        │   uploaded (§5, §9)
        │
        ├─→ AI-visibility: live LLM Responses calls if connected, or READ
        │   manually-entered `ai_mentions` if not (§6)
        │
        ├─→ Manual-only data: links, activities, screenshots for the month
        │
        ├─→ Narrative: auto-drafted via Groq (§6), staff edits before publish
        │
        └─→ Compute derived figures → write `report_months` draft
            (generated_at set here, distinct from published_at)

Staff reviews, edits narrative → Publish → status='published', published_at set
```

Concurrency: `report_months` has `unique(client_id, month)` at the DB level,
plus a lock (Postgres advisory lock, or a status check-and-set) around
generation so two simultaneous clicks for the same client-month can't both
proceed.

---

## 11. Data model

```sql
-- Single-account, internal use. No parent_id, no reseller hierarchy — if
-- that becomes relevant later it gets designed then, not pre-shaped now.
accounts
  id            uuid pk default gen_random_uuid()
  name          text                          -- single row: 'EZ Rankings'
  created_at    timestamptz default now()

users
  id              uuid pk default gen_random_uuid()
  account_id      uuid references accounts(id)
  email           citext unique
  password_hash   text                  -- bcrypt/argon2, never plaintext.
                                         -- Added when Phase 12 surfaced that
                                         -- no authentication mechanism had
                                         -- been built in any earlier phase —
                                         -- RBAC needs identity to check a
                                         -- role against, and this was missing.
  role            enum('agency_admin','agency_staff')
  last_login_at   timestamptz null

clients
  id                uuid pk default gen_random_uuid()
  account_id        uuid references accounts(id)
  name              text
  domain            text
  logo_url          text null               -- the CLIENT's own logo, shown
                                             -- on their own report
  business_type     enum('ecommerce','leadgen','local','saas')
  locale            text
  package_keywords  int
  status            enum('active','paused','churned')
  onboarded_at      date

client_sections
  client_id     uuid references clients(id)
  section_key   text                     -- 'rankings','ai_visibility','conversions','local',…
  enabled       boolean
  primary key (client_id, section_key)

-- One row per data source per client. GSC/GA4/GBP: service-account access,
-- shared credential referenced once at the app level (§7) — only property_id
-- and status vary per client. DataForSEO: a real per-client key if supplied,
-- or the platform default.
connections
  id                uuid pk default gen_random_uuid()
  client_id         uuid references clients(id)
  provider          enum('gsc','ga4','gbp','dataforseo')
  access_mode       enum('platform_shared','client_owned')
  credentials       jsonb null            -- ENCRYPTED. Meaningful only for
                                           -- dataforseo/client_owned; gsc/ga4/gbp
                                           -- reference the one shared
                                           -- service-account key, not a per-row secret
  property_id       text                  -- GA4 property / GSC site / GBP location
  property_tz       text null             -- Timezone used for this
                                           -- connection's month-boundary
                                           -- computation (§10, §14). GA4:
                                           -- auto-detected from the
                                           -- property. GBP: no timezone is
                                           -- exposed by either the
                                           -- Performance or Business
                                           -- Information API — staff enters
                                           -- it manually at onboarding
                                           -- (they already know the
                                           -- client's city). Never derive
                                           -- this from a postal region code
                                           -- — country-level derivation is
                                           -- lossy for large countries.
                                           -- GSC has no per-property
                                           -- timezone concept, stays null.
  status            enum('connected','error','expired','not_connected')
  last_verified_at  timestamptz null      -- set by "Verify connection" (§7)
  last_sync_at      timestamptz null
  last_error        text null

keywords
  id              uuid pk default gen_random_uuid()
  client_id       uuid references clients(id)
  term            text
  group_tag       text null
  target_url      text null
  search_volume   int null
  initial_rank    int null
  is_active       boolean default true
  added_at        date

rankings
  keyword_id            uuid references keywords(id)
  captured_on           date
  position              int null
  url                   text null
  ai_overview_present   boolean null   -- bundled load_async_ai_overview flag (§4)
  source                enum('api','manual')
  primary key (keyword_id, captured_on)

-- DataForSEO async task tracking (rankings only — Standard method is async)
provider_tasks
  id              uuid pk default gen_random_uuid()
  connection_id   uuid references connections(id)
  sync_run_id     uuid null references sync_runs(id)  -- links each task back
                                                        -- to its submission
                                                        -- batch, so the batch's
                                                        -- completion can be
                                                        -- reconciled (§5)
  task_id         text
  tag             text                  -- "{client_id}:{keyword_id}:{date}"
  status          enum('pending','completed','failed')
  submitted_at    timestamptz
  completed_at    timestamptz null
  cost            numeric null

ai_prompts
  id              uuid pk default gen_random_uuid()
  client_id       uuid references clients(id)
  prompt_text     text
  is_active       boolean default true
  added_at        date

ai_mentions
  id              uuid pk default gen_random_uuid()
  client_id       uuid references clients(id)
  prompt_id       uuid null references ai_prompts(id)
  platform        enum('chatgpt','claude','gemini','perplexity')
  captured_on     date
  mentioned       boolean null
  cited_pages     jsonb null            -- [{page, prompt_count}, ...]
  source          enum('llm_responses_custom','manual')
  raw_response    text null

metrics
  client_id       uuid references clients(id)
  provider        text
  metric_key      text                  -- 'clicks','sessions','organic_revenue',…
  dimension_key   text null             -- 'page','channel','device','country'
  dimension_value text null
  captured_on     date
  value           numeric
  source          enum('api','manual')
  primary key (client_id, provider, metric_key, coalesce(dimension_key,''), coalesce(dimension_value,''), captured_on)

links
  id              uuid pk default gen_random_uuid()
  client_id       uuid references clients(id)
  created_on      date
  activity_type   text
  domain          text
  url             text
  status          enum('active','removed','pending')
  last_checked    timestamptz null      -- set by the liveness re-checker (§12)
  dr              int null

activities
  id            uuid pk default gen_random_uuid()
  client_id     uuid references clients(id)
  month         date
  activity_type text
  count         int
  notes         text null

screenshots
  id            uuid pk default gen_random_uuid()
  client_id     uuid references clients(id)
  month         date
  keyword_id    uuid null references keywords(id)
  file_url      text
  caption       text null

-- generated_at and published_at are distinct — a report can be drafted well
-- before it's published.
report_months
  id              uuid pk default gen_random_uuid()
  client_id       uuid references clients(id)
  month           date
  status          enum('draft','review','published')
  snapshot        jsonb                 -- frozen numbers as published
  narrative       text null             -- starts LLM-drafted (§6), staff-edited
  next_month_plan jsonb null
  generated_at    timestamptz null
  published_at    timestamptz null
  published_by    uuid null references users(id)
  unique (client_id, month)

-- Every pull, scheduled or click-triggered, success or failure. Also the
-- generic cost-log for any paid DataForSEO call that doesn't have a
-- dedicated task-tracking table of its own (keyword research, AI-visibility)
-- — provider_tasks.cost covers rankings specifically (§5); everything else
-- logs its cost here, even a single on-demand lookup. A lightweight
-- cost-only row is fine — this doesn't imply a long-running job, it's
-- what makes §14's cost guardrail actually see every dollar spent, not
-- just the rankings pipeline's.
sync_runs
  id            uuid pk default gen_random_uuid()
  client_id     uuid references clients(id)
  provider      text
  started_at    timestamptz
  finished_at   timestamptz null
  status        enum('success','partial','failed')
  rows          int null
  cost          numeric null
  error         text null
```

---

## 12. Link liveness re-checker

A scheduled job (weekly — link status doesn't change as fast as rankings)
re-checks each active link's URL, updates `links.last_checked` and
`links.status` if it's gone dead. Same retry/log pattern as §13.

---

## 13. Reliability

1. **Retry** — 3x exponential backoff on any external call failure (rankings
   job, AI-visibility calls, GSC/GA4/GBP pulls, link liveness checks)
2. **Alert** — after retries are exhausted, `connections.status = 'error'`,
   agency notified (Slack/email)
3. **Log** — every run recorded in `sync_runs`, success or failure

---

## 14. Production requirements

**Testing:** no feature is done without a test that would fail if the logic
broke. Unit tests (pytest) for anything that computes or decides (snapshot
calculation, mention-analysis logic, credential validation). Integration
tests for every connector. A contract test for the webhook handler
specifically — a correctly-tagged payload writes, an incorrectly-tagged one
doesn't.

**CI/CD:** lint, type-check, full test suite, build — on every push. Normal
platform-native deployment (Railway/Render or equivalent) — no shared-hosting
workarounds needed here, unlike an earlier draft of this document written
against cPanel constraints. Migrations run via Alembic as part of the deploy
step. Staging auto-deploys on merge to main; production deploy is a manual,
explicit trigger, mirroring the human-in-the-loop principle already applied
to publishing a report.

**Secrets:** no secret ever committed to git. Separate credentials per
environment. **Envelope encryption** for `connections.credentials` — encrypt
each row with a data-key, encrypt that data-key with a master key — so
rotating the master key later doesn't require re-encrypting every stored
credential at once.

**Observability:** structured (JSON) logs across the FastAPI app and Celery
workers. Error tracking (Sentry or equivalent) with `client_id`/`provider`/
`task_id` context on every exception. `sync_runs` is the business-level audit
log; this is the engineering-level layer underneath it. Liveness/readiness
health checks, not one flat endpoint.

**Cost guardrails — the most concrete risk given how usage-based every paid
provider here is.** A daily job sums `provider_tasks.cost` (rankings) and
`sync_runs.cost` (every other paid DataForSEO call — AI-visibility, keyword
research, anything added later that doesn't have its own task-table) per
provider per day. If a day's spend exceeds a configured multiple of its
expected average (e.g., 3x), pause that provider's job and alert
immediately — same channel as connection errors. Build this *before* real
spend exists to protect against, not after a bill surprises someone.

**RBAC:** a FastAPI dependency checks the authenticated user's role against
each route's required role before the handler runs — enforced at the route
layer, not by hiding a button in React. `agency_staff` can view and draft,
cannot publish. `agency_admin` has full access including publish and
connection management.

**Concurrency/idempotency:** `report_months` unique constraint (§10). Tag-based
upsert already makes the rankings webhook idempotent on retry — confirm with
DataForSEO support whether a retried `task_post` could double-charge.

**Input validation:** manual CSV upload validates the fixed column schema,
rejects malformed rows individually with a specific error, not a silent skip
or a whole-batch failure. Manual forms validate server-side (Pydantic
models), not client-side only. Free-text fields (narrative, notes, captions)
get standard sanitization before storage.

**Timezone handling:** all stored timestamps are UTC. Month boundaries for
report generation use each connection's own `property_tz` (§7, §11) — not a
hardcoded IST assumption, since a client's GA4 property may be configured in
a different timezone.

---

## 15. UI notes

The FoodBazaar prototype's design (sage-canvas + wine-accent palette,
Bricolage Grotesque/Inter/IBM Plex Mono type system) is kept as the visual
language for the **report-viewer screens**, rebuilt in React — it already
avoids generic-AI defaults and has real typographic roles (mono = sourced
fact, Inter = human voice).

**The one rule carried forward as load-bearing, not decorative:** every
number shown carries a small provenance caption naming its source and
automated/manual status (`GSC · daily`, `Agency: manual entry`) — this is the
whole point of the system (a human-reviewed, source-verifiable replacement
for a spreadsheet), so it's non-negotiable wherever a number appears.

**Admin/back-office screens** (connections, keyword/prompt management, manual
entry forms, user management) are **not separately designed** — build them
functional, using standard React form/table patterns, decided during
implementation rather than specified here. These are staff-only tools in
Phase 1, not the client-facing artifact the design language above exists to
support.

---

## 16. Deferred / not in scope

**White-label / reseller / client-facing login** — parked entirely, not even
as schema-readiness. Redesigned fresh if and when it's actually pursued.

**Alternatives evaluated and rejected, with the condition to revisit each:**

| Alternative | Lost to | Re-open if |
|---|---|---|
| DataForSEO LLM Mentions API | LLM Responses + custom analysis (§6) | Combined usage would exceed its $100/mo floor anyway |
| Otterly.ai (AI-visibility) | LLM Responses + custom analysis | Custom analysis logic becomes a genuine maintenance burden |
| Semrush AI Toolkit | DataForSEO-based approach | Not likely — most expensive option evaluated |
| Mangools SERPWatcher (rankings) | DataForSEO SERP API | Total tracked keywords regularly exceed ~5,000/month |
| Standard OAuth (GSC/GA4/GBP) | Google service accounts (§7) | Not likely — the verification-gate problem is structural, not situational |
| PHP/Laravel/MySQL, cPanel shared hosting | Python/FastAPI/Postgres(Supabase)/React | Not likely — this was a deliberate stack reversal, not a constraint discovered mid-build |

**Phase 2+ (not scoped in detail):** GBP Reviews (needs a Google
access-request with real lead time), competitor analysis (DataForSEO Labs),
backlink quality scoring, technical health audits, basic PDF export
refinement.

---

## 17. Build order

**Phase 1 — spine.** Schema (§11). Service-account connectors for GSC/GA4/GBP
with manual fallback for each (§9). Rankings: DataForSEO nightly job +
manual fallback (§5). AI-visibility: LLM Responses + custom analysis + manual
fallback (§6). Narrative auto-draft. Snapshot/publish flow (§10). Basic
(non-branded) PDF export. Cost guardrails (§14) built before real spend
exists. Agency-facing view only.

**Phase 2.** Link liveness re-checker (§12) as a real job if not already
live. Manual entry forms polish. GBP Reviews, if pursued.

**Phase 3+.** Everything in §16 — designed fresh when actually needed.