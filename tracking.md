# EZ Rankings SEO Dashboard — Tracking

**Instructions for the coding agent (Antigravity): populate and maintain this
file as you build. Nothing below is pre-filled — derive it from
`architecture.md`, the only other file in this project.**

This single file covers three things that used to be three files — kept
together now for less overhead, not because they're the same kind of
information. Keep them in their own sections, don't blend them.

---

## Part A — Phases (sequencing, changes only when scope changes)

Status legend: 🔲 Not started · 🔶 In progress · ✅ Done · ⏸️ Blocked/parked

### Phase 1 — Spine

**Status:** 🔶 In progress

**Goal:** End-to-end internal system: schema, all connectors (GSC/GA4/GBP +
DataForSEO), rankings nightly job, AI-visibility pipeline, narrative
auto-draft, snapshot/publish flow, cost guardrails, basic PDF export,
agency-facing view only.

**Includes:**
- Database schema (§11)
- Service-account connectors for GSC / GA4 / GBP with manual fallback (§7, §9)
- Rankings: DataForSEO nightly job + manual fallback (§5)
- AI-visibility: LLM Responses + custom analysis + manual fallback (§6)
- Narrative auto-draft (§6)
- Snapshot / publish flow (§10)
- Basic (non-branded) PDF export
- [x] Phase 10: Nightly Cost Guardrails
- [x] Phase 11: Generate Report Pipeline
- [ ] Phase 12: Role-Based Access Control (RBAC)
- RBAC (§14)
- Testing & CI/CD infrastructure (§14)
- Reliability: retry, alert, logging (§13)
- Secrets / envelope encryption (§14)
- Observability: structured logs, error tracking, health checks (§14)
- Keyword research on-demand (§8)
- Manual entry for all sources (§9)

**Gated by:** Nothing — first phase.

---

### Phase 2

**Status:** 🔲 Not started

**Goal:** Polish and secondary features.

**Includes:**
- Link liveness re-checker as a real scheduled job (§12)
- Manual entry forms polish (e.g. 'Keyword ID' should be a searchable dropdown/autocomplete by keyword term instead of a raw UUID text field)
- GBP Reviews (if pursued — needs Google access-request lead time)

## Known Gaps & Intentionally Deferred Items

1. **AI-visibility Section 3 (AI-referral traffic) not built** — GA4 pipeline (Phase 4/16) never captured a referrer/AI-platform dimension, only channel/device/country. Revisit if the GA4 ingestion is extended to capture this dimension.
2. **Missing Granular Error Boundaries**: Top-level API crashes take down entire page segments.
3. **Keyword Dropdown**: Keyword ID in manual rankings entry is a raw UUID text field. A searchable dropdown by keyword term is deferred to UX polish phase.
4. **GA4 property_tz auto-detection** (architecture.md §7) was never wired into Phase 3/4's backend — the field is currently manual-entry only, identical to GBP. Revisit if GA4's actual property-timezone API becomes available.

**Gated by:** Phase 1 complete.

---

### Phase 3+

**Status:** 🔲 Not started

**Goal:** Everything deferred in §16 — designed fresh when needed.

**Includes:**
- White-label / reseller / client-facing login
- Competitor analysis (DataForSEO Labs)
- Backlink quality scoring
- Technical health audits
- PDF export refinement
- GBP Reviews (if not done in Phase 2)

**Gated by:** Phase 2 complete; each item designed from scratch when pursued.

---

## Part B — Features (granular checklist, update as you build)

Status legend: 🔲 Not started · 🔶 In progress · ✅ Done · ⏸️ Blocked/parked

### Foundation

| Feature | Status | Architecture ref | Notes |
|---|---|---|---|
| FastAPI project structure (app/, tests/, alembic/) | ✅ | §2 | Python 3.11, standard layout |
| Postgres connection config (Supabase) | ✅ | §2 | .env-driven, SQLAlchemy ORM |
| Celery + Redis connection config | ✅ | §2 | Infrastructure only, no jobs yet |
| Alembic migrations — all 16 tables (§11) | ✅ | §11 | FK-order: accounts → users → clients → client_sections → connections → keywords → rankings → provider_tasks → ai_prompts → ai_mentions → metrics → links → activities → screenshots → report_months → sync_runs |
| SQLAlchemy models — all 16 tables | ✅ | §11 | Relationships matching §11 |
| Postgres ENUM types (role, business_type, client_status, provider, access_mode, conn_status, ranking_source, task_status, ai_platform, ai_source, metric_source, link_status, report_status, sync_status) | ✅ | §11 | Native PG ENUMs, not CHECK constraints |
| Composite PK: rankings (keyword_id, captured_on) | ✅ | §11 | |
| Composite PK: client_sections (client_id, section_key) | ✅ | §11 | |
| Composite PK: metrics (with coalesce) | ✅ | §11 | coalesce(dimension_key,''), coalesce(dimension_value,'') |
| UNIQUE constraint: report_months (client_id, month) | ✅ | §10, §11 | Load-bearing for concurrency design |
| jsonb columns: connections.credentials, ai_mentions.cited_pages, report_months.snapshot, report_months.next_month_plan | ✅ | §11 | Only where §11 specifies |
| uuid PKs with gen_random_uuid() default | ✅ | §11 | pgcrypto if needed |
| pytest infrastructure (real Postgres) | ✅ | §14 | Not SQLite — need enum/jsonb/uuid coverage |
| Migration tests (table existence + constraints) | ✅ | §14 | Including report_months unique-constraint rejection test |
| CI pipeline (GitHub Actions) | ✅ | §14 | lint + type-check + PG service + alembic + pytest |
| Docker: Dockerfile + docker-compose.yml | ✅ | §2 | App + Postgres + Redis + Celery worker |
| Health check: liveness route | ✅ | §14 | Process-up check |
| Health check: readiness route | ✅ | §14 | Postgres connectivity via actual query |

### Service-account connectors (§7)

| Feature | Status | Architecture ref | Notes |
|---|---|---|---|
| Google Service-Account credential loading | ✅ | §7 | `GOOGLE_SERVICE_ACCOUNT_JSON` loaded via `google-auth` |
| Connection records CRUD | ✅ | §7, §11 | Scoped to gsc, ga4, gbp |
| GSC connector (data-pulling) | ✅ | §7 | Shared service-account, property_id scoped |
| GA4 connector (data-pulling) | ✅ | §7 | Shared service-account, property_id scoped |
| GBP connector (data-pulling) | 🔲 | §7 | Shared service-account, property_id scoped |
| "Verify connection" action per provider | ✅ | §7 | Lightweight test API call |
| Periodic access re-verification | 🔲 | §7 | Surfaces revoked grants as status='error' |

### Rankings (§5)

| Feature | Status | Architecture ref | Notes |
|---|---|---|---|
| Celery beat nightly job — batch keyword tasks | 🔲 | §5 | Standard method (not Live), 3x cheaper |
| load_async_ai_overview flag on SERP requests | 🔲 | §4, §5 | Bundled, not separate |
| Postback webhook route — receive DataForSEO results | 🔲 | §5 | Tag-based matching |
| Upsert rankings from webhook | 🔲 | §5 | source='api' |
| provider_tasks crash recovery | 🔲 | §5 | Save task_id immediately |
| Manual CSV upload for rankings | 🔲 | §5, §9 | source='manual', same table |
| Per-keyword manual entry form | 🔲 | §5, §9 | source='manual' |

### AI-visibility (§6)

| Feature | Status | Architecture ref | Notes |
|---|---|---|---|
| LLM Responses API integration (ChatGPT, Claude, Gemini, Perplexity) | 🔲 | §6 | DataForSEO LLM Responses API |
| Custom analysis via Groq — mention count + cited pages | 🔲 | §6 | |
| ai_prompts management (CRUD) | 🔲 | §6 | Tracked-prompts list per client |
| Manual fallback — per-platform entry form | 🔲 | §6, §9 | source='manual' |
| Narrative auto-draft via Groq | 🔲 | §6 | LLM-generated, staff-edited |

### Keyword research (§8)

| Feature | Status | Architecture ref | Notes |
|---|---|---|---|
| DataForSEO Keyword Data API — on-demand lookup | ✅ | §8 | Sets keywords.search_volume once |

### Manual entry — all sources (§9)

| Feature | Status | Architecture ref | Notes |
|---|---|---|---|
| Rankings CSV upload + per-keyword form | 🔲 | §9 | Covered under Rankings section |
| AI-visibility per-platform form | ✅ | §9 | Manual fallback form implemented |
| GSC manual entry form | ✅ | §9 | metrics table, source='manual' |
| GA4 manual entry form | ✅ | §9 | metrics table, source='manual' |
| GBP manual entry form | 🔲 | §9 | metrics table, source='manual' |
| Backlinks manual entry form | 🔲 | §9 | links table (always manual) |
| Content activity manual entry form | 🔲 | §9 | activities table (always manual) |
| Screenshots manual entry form | 🔲 | §9 | screenshots table (always manual) |

### Report pipeline (§10)

| Feature | Status | Architecture ref | Notes |
|---|---|---|---|
| "Generate Report" flow — pull/read all sources | 🔲 | §10 | GSC/GA4/GBP live-pull if connected, else manual data |
| Derived-figure computation | 🔲 | §10 | Compute from raw data |
| Write report_months draft | 🔲 | §10 | generated_at set at creation |
| Staff review + narrative editing | 🔲 | §10 | |
| Publish flow — status='published', published_at set | 🔲 | §10 | |
| Concurrency control (advisory lock or check-and-set) | 🔲 | §10 | On top of unique(client_id, month) |
| Basic PDF export (non-branded) | 🔲 | §10 | |

### Cost guardrails (§14)

| Feature | Status | Architecture ref | Notes |
|---|---|---|---|
| Daily cost aggregation job | ✅ | §14 | Sum provider_tasks.cost + sync_runs.cost. Materialized in daily_provider_costs table |
| Threshold breach detection (configurable multiplier) | ✅ | §14 | 3x rolling avg. Edge-case handled via configurable floor limit for first 3 days |
| Auto-pause provider job on breach | ✅ | §14 | Added ProviderState pause gate to Rankings job |
| Alert on breach (same channel as connection errors) | ✅ | §14 | Slack/email stub `alert_agency` |

### RBAC (§14)

| Feature | Status | Architecture ref | Notes |
|---|---|---|---|
| FastAPI dependency — role check per route | 🔲 | §14 | Route-layer enforcement, not UI-only |
| agency_staff: view + draft only | 🔲 | §14 | Cannot publish |
| agency_admin: full access including publish + connections | 🔲 | §14 | |

### Link liveness (§12) — Phase 2

| Feature | Status | Architecture ref | Notes |
|---|---|---|---|
| Check link liveness on report generation day | ✅ | §12 | Updates links.last_checked + status |

### Reliability / security (§13, §14)

| Feature | Status | Architecture ref | Notes |
|---|---|---|---|
| Retry — 3x exponential backoff on external calls | 🔲 | §13 | All connectors + link checker |
| Alert — connection errors after retries exhausted | ✅ | §13 | DB status update implemented |
| Real Slack/email alert integration | ✅ | §13 | SMTP fallback alerting implemented via alerting.py |
| sync_runs logging — every run recorded | 🔲 | §13 | Success or failure |
| Envelope encryption for connections.credentials | 🔲 | §14 | Data-key per row, master key wraps |
| Service-account key rotation policy | 🔲 | §7, §14 | Larger blast radius mitigation |
| Input validation — CSV upload schema enforcement | 🔲 | §14 | Per-row rejection, not batch failure |
| Input validation — Pydantic server-side | 🔲 | §14 | Not client-side only |
| Free-text sanitization | 🔲 | §14 | narrative, notes, captions |
| Timezone handling — UTC storage, property_tz for boundaries | 🔲 | §14 | |

### Production infra (§14)

| Feature | Status | Architecture ref | Notes |
|---|---|---|---|
| Structured JSON logging (FastAPI + Celery) | 🔲 | §14 | |
| Error tracking (Sentry or equivalent) | 🔲 | §14 | client_id/provider/task_id context |
| Staging auto-deploy on merge to main | ✅ | §14 | Railway/Render |
| Production deploy — manual trigger only | ✅ | §14 | |

---

## Part C — Progress log (dated, evidence-based, append-only)

<!-- New entries go here, most recent first. Nothing pre-filled. -->

### 2026-08-16 — Phase 9: Keyword Research Complete
**Work Completed:**
- Integrated DataForSEO's Keyword Data Live API (`/api/clients/{client_id}/keyword-research`).
- Built `Keywords` CRUD endpoints (`/api/clients/{client_id}/keywords`) with support for an optional `fetch_metrics` flag to synchronously pull and save `search_volume` during keyword creation.
- 5/5 integration tests passing.

### 2026-08-16 — Phase 8: AI-Visibility Complete
**Work Completed:**
- Built `AiPrompts` CRUD endpoints (`/api/clients/{client_id}/ai_prompts`).
- Added manual fallback endpoint (`/api/clients/{client_id}/ai_mentions/manual`).
- Created `trigger_ai_visibility_pull_on_demand` job (on-demand, not beat-scheduled as per §5 and §10) that fetches Live DataForSEO LLM Responses for ChatGPT, Claude, Gemini, and Perplexity.
- Implemented Groq extraction using `llama-3.1-8b-instant` to strictly parse brand mentions and citations.
- Validated with 7 integration/unit tests.

### 2026-08-14 — Service Account Connectors
**Work Completed:**
- Added `GOOGLE_SERVICE_ACCOUNT_JSON` loading via `google-auth`.
- Built connection records CRUD routes scoped to `gsc`, `ga4`, `gbp`.
- Implemented `/verify` endpoint making lightweight test API calls to `searchanalytics`, `runReport`, and `businessprofileperformance`.
- Successfully validated 11 integration tests under Docker utilizing mock injections. 0 linting and 0 typing errors remaining.

**Evidence:**
```
tests/test_google_auth.py::test_get_google_credentials_missing_env_vars PASSED [  9%]
tests/test_google_auth.py::test_get_google_credentials_invalid_json PASSED [ 18%]
tests/test_google_auth.py::test_get_google_credentials_valid_raw_json PASSED [ 27%]
tests/test_connections.py::test_create_connection PASSED                 [ 36%]
tests/test_connections.py::test_update_connection_resets_status PASSED   [ 45%]
tests/test_connections.py::test_verify_gsc_wrapper_success PASSED        [ 54%]
tests/test_connections.py::test_verify_gsc_wrapper_failure PASSED        [ 63%]
tests/test_connections.py::test_verify_gsc_real_mock_error PASSED        [ 72%]
tests/test_connections.py::test_verify_ga4_invalid_argument PASSED       [ 81%]
tests/test_connections.py::test_verify_ga4_permission_denied PASSED      [ 90%]
tests/test_connections.py::test_verify_gbp_success PASSED                [100%]

============================== 11 passed in 1.43s ==============================
```

### 2026-08-14 — Upgraded to Python 3.11

**Work Completed:**
- Upgraded target Python version across the project (`pyproject.toml`, mypy, ruff, `Dockerfile`, and CI pipeline) to Python 3.11.
- Eliminated Python 3.9 compatibility downgrades by enabling ruff's `UP007` rule and auto-restoring native `X | Y` union type syntax across all SQLAlchemy models.
- Verified test suite and static analysis inside a Python 3.11 container.

**Evidence:**
- Test Suite: `pytest -v` inside Python 3.11 container passed all 52 tests.
- Linting: `ruff check` reports 0 errors.
- Types: `mypy app/` reports 0 issues.

### 2026-08-14 — Foundation Built

**Work Completed:**
- Fully initialized the FastAPI project with `app/`, `tests/`, and `alembic/` structure.
- Configured real PostgreSQL connection + Celery/Redis infrastructure.
- Defined all 16 SQLAlchemy models strictly adhering to Architecture §11 schema constraints.
- Created all 16 Alembic migrations, correctly executing `CREATE TYPE AS ENUM` for Postgres native enums.
- Implemented `/health/live` and `/health/ready` routes (the latter executes a real DB query).
- Setup `pytest` infrastructure utilizing a real Docker-backed Postgres container.
- Wrote 52 tests verifying table existence, columns, constraint compliance (including the load-bearing `report_months` composite unique constraint and the `metrics` coalesced unique index). **All 52 tests are passing.**
- Integrated Python 3.11 native union type hints (`X | Y`).
- Integrated `ruff` (linting) and `mypy` (type-checking), both currently passing with 0 errors.
- Added `Dockerfile` and `docker-compose.yml` for local multi-container bring-up.
- Configured GitHub Actions `.github/workflows/ci.yml` with CI (lint/type-check/test) and CD (staging auto-deploy, production manual-trigger).

**Evidence:**
- Migrations apply cleanly: `alembic upgrade head` completes.
- Test Suite: `pytest -v` results in 52/52 passed.
- Linting: `ruff check .` returns "All checks passed!".
- Types: `mypy app/` returns "Success: no issues found".
- Container: `docker-compose up` cleanly starts postgres, redis, app, and celery-worker.

### 2026-08-16 — Phase 3: GSC Data-Pulling Logic

**Work Completed:**
- Added `tenacity` library to `requirements.txt` to handle retries for transient Google API failures.
- Implemented `app/services/gsc_service.py` to pull site, page, and query level metrics (clicks, impressions, ctr, position) via `google-analytics-data` and write them to the `metrics` table (source=api).
- Added retry mechanism using `tenacity` for resilience as mandated in §13.
- Integrated `SyncRun` tracking for every API sync pull, logging success, rows inserted, and failure messages, automatically updating the Connection's state.
- Created `POST /clients/{client_id}/manual-gsc` route with Pydantic validation (clicks/impressions >= 0, ctr 0-1, position > 0) to insert metrics manually into the database (source=manual) as per §9.
- Added 5 automated tests covering successful pull, empty data response, transient retry-then-failure, and the manual entry logic (both success and validation failures).

**Evidence:**
- Test Suite: `pytest -v tests/test_gsc_service.py tests/test_manual_metrics.py` completes with `5 passed, 4 warnings in 5.02s` inside the docker container.
- Linting: `ruff check --fix .` executed cleanly.
- Types: `mypy app/ tests/` executes successfully with `Success: no issues found in 38 source files`.

### 2026-08-16 — Phase 4: GA4 Data-Pulling Logic

**Work Completed:**
- Implemented `app/services/ga4_service.py` with timezone-aware `property_tz` bounds calculating previous month logic and executing parallel dimensional queries against GA4 API.
- Integrated `SyncRun` tracking and tenacity retry wrapper identical to Phase 3.
- Wired `/connections/{connection_id}/pull` to support `ga4` natively.
- Added `POST /clients/{client_id}/manual-ga4` manual fallback form with identical server-side Pydantic validation for sessions, users, engaged_sessions, conversions, and revenue.
- Added 4 test cases verifying exact DB states, mock retries, missing dimensions, and explicit timezone calculation validation (`test_property_tz_date_computation`).
- Verified zero MyPy and Ruff errors remain.

**Evidence:**
```
============================= test session starts ==============================
platform linux -- Python 3.11.15, pytest-8.3.3, pluggy-1.6.0 -- /usr/local/bin/python3.11
cachedir: .pytest_cache
rootdir: /app
configfile: pyproject.toml
plugins: anyio-4.14.2
collecting ... collected 9 items

tests/test_ga4_service.py::test_property_tz_date_computation PASSED
tests/test_ga4_service.py::test_pull_ga4_data_success PASSED
tests/test_ga4_service.py::test_pull_ga4_data_empty_success PASSED
tests/test_ga4_service.py::test_pull_ga4_data_retry_failure PASSED
tests/test_ga4_service.py::test_ga4_pull_endpoint_integration 
--- ACTUAL GA4 /pull RESPONSE BODY ---
{'status': 'success', 'rows_inserted': 5}
--------------------------------------

PASSED
tests/test_manual_metrics.py::test_manual_ga4_success PASSED
tests/test_manual_metrics.py::test_manual_ga4_validation_errors PASSED
tests/test_manual_metrics.py::test_manual_ga4_malformed PASSED

============================== 9 passed in 4.31s ===============================
```

## Phase 5: GBP Data-Pulling Logic

**Work Completed:**
- Extracted timezone-aware `calculate_previous_month()` into `app/services/date_utils.py` for shared use across GA4 and GBP.
- Implemented `app/services/gbp_service.py` using `fetchMultiDailyMetricsTimeSeries` batch endpoint to pull all 8 perform- GA4 property_tz auto-detection (architecture.md §7) was never wired into Phase 3/4's backend — the field is currently manual-entry only, identical to GBP. Revisit if GA4's actual property-timezone API becomes available.

## Phase 20: Admin Settings UI (Users, Keywords, AI Prompts)
- **Status:** Complete
- **Details:** Added `is_active` to users, applied RBAC, and created React tests for Admin UIs. Fixed test environment dependency injection.
- Integrated `SyncRun` tracking and tenacity retry wrapper identical to Phase 3/4.
- Wired `/connections/{connection_id}/pull` to support `gbp` natively.
- Added `POST /clients/{client_id}/manual-gbp` manual fallback form with identical server-side Pydantic validation.
- Validated all 8 metrics correctly map into the database using explicit DB verifications in tests.
- Addressed GA4 test cross-contamination by scoping query in `test_pull_ga4_data_success` to `client_id` explicitly.

**Evidence:**
```
============================= test session starts ==============================
platform linux -- Python 3.11.15, pytest-8.3.3, pluggy-1.6.0 -- /usr/local/bin/python3.11
cachedir: .pytest_cache
rootdir: /app
configfile: pyproject.toml
plugins: anyio-4.14.2
collecting ... collected 18 items

tests/test_gbp_service.py::test_pull_gbp_data_success 
--- ACTUAL GBP DB ROWS (ALL 8 METRICS) ---
metric_key=impressions_desktop_maps | value=120.0 | captured_on=2026-07-15
metric_key=impressions_desktop_search | value=350.0 | captured_on=2026-07-15
metric_key=impressions_mobile_maps | value=480.0 | captured_on=2026-07-15
metric_key=impressions_mobile_search | value=610.0 | captured_on=2026-07-15
metric_key=calls | value=25.0 | captured_on=2026-07-15
metric_key=direction_requests | value=42.0 | captured_on=2026-07-15
metric_key=website_clicks | value=88.0 | captured_on=2026-07-15
metric_key=bookings | value=7.0 | captured_on=2026-07-15
------------------------------------------
PASSED
tests/test_gbp_service.py::test_pull_gbp_data_empty_success PASSED
tests/test_gbp_service.py::test_pull_gbp_data_retry_failure PASSED
tests/test_gbp_service.py::test_gbp_pull_endpoint_integration 
--- ACTUAL GBP /pull RESPONSE BODY ---
{'status': 'success', 'rows_inserted': 3}
--------------------------------------
PASSED
tests/test_manual_metrics.py::test_manual_gbp_success 
--- ACTUAL GBP MANUAL DB ROWS (ALL 8 METRICS) ---
metric_key=bookings | value=7.0
metric_key=calls | value=25.0
metric_key=direction_requests | value=42.0
metric_key=impressions_desktop_maps | value=120.0
metric_key=impressions_desktop_search | value=350.0
metric_key=impressions_mobile_maps | value=480.0
metric_key=impressions_mobile_search | value=610.0
metric_key=website_clicks | value=88.0
-------------------------------------------------
PASSED
tests/test_manual_metrics.py::test_manual_gbp_validation_errors PASSED
tests/test_manual_metrics.py::test_manual_gbp_malformed PASSED

tests/test_ga4_service.py::test_pull_ga4_data_success PASSED
(and 10 other tests passing...)

============================== 18 passed in 9.26s ==============================
All checks passed!
```