# CLAUDE.md

Guide for Claude Code (and any developer) working on this repository. **Read it before making
changes and keep it up to date**: whenever a decision, convention, module or pending item changes,
update this file in the same commit.

## Project

**IMSI** — Integrated Management System for School Industries, for *Industrias Escolares* (school
furniture manufacturer). Software Engineering II, Universidad Nacional de Colombia, 2026-2.
Team *Testigos de Meluk*: Cristofer Ordoñez, Andrés Franco, Carlos Cuervo, Juan Sebastián Gil.

Sources of truth, in order of precedence:

1. `Workshops/Corrections/README.md` — corrections to the Workshop 1/2 deliverables (what changes and
   what is kept). **It overrides the PDFs, mockups and diagrams** wherever they conflict.
2. `Workshops/Workshop-1/` (analysis: requirements, user stories) and `Workshops/Workshop-2/`
   (design: BPMN, class diagram, mockups, DB model, architecture).
3. `backend/README.md` — architecture rules, module template, commands.

## Conventions

- **Language:** code, comments, commit messages and documentation in **English**. Everything the end
  user sees (UI labels, error messages, emails, PDFs, status names such as "Conciliada") in
  **Spanish**.
- **Git:** work on `feat/first-release` (not pushed to `main`; no PR until the first release is
  ready). Conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`). Commit only when the user asks.
  **No AI attribution**: commit messages and PR descriptions never carry `Co-Authored-By: Claude…`
  or "Generated with Claude Code" lines (team decision, November 2026).
- **Never** commit `.env` or secrets. Use synthetic data in tests (NFR-05-02).
- GitHub Actions / CI: postponed (not configured yet).

## Stack and how to run

- Backend: Python 3.12, Django 5.2 LTS, DRF, drf-spectacular, Celery + Beat, PostgreSQL 16, Redis.
- Frontend: React 19 + TypeScript + Vite 7 (SPA, client-side rendering), React Router 7,
  TanStack Query 5, React Hook Form + Zod 4, Tailwind CSS 4.
- Everything runs locally with Docker Compose (`docker compose up --build`), see root `README.md`.
  Services: db, redis, mailpit (emails at :8025), backend (:8000), worker, beat, frontend (:5173).
- Tests: `docker compose exec backend pytest` (always uses `config.settings.test` via `--ds`).
  Quality: `ruff check .`, `ruff format .`, `lint-imports`. Frontend: `npm run build` (type-checks).
- API docs: Swagger `/api/docs/`, ReDoc `/api/redoc/`, schema `/api/schema/`.
- First user: `python manage.py create_superadmin --email … --name …`; recovery:
  `python manage.py reset_password --email … [--reset-authenticator]`.

## Architecture (must be respected)

Modular monolith; **every module is hexagonal** with four layers:

```
backend/modules/<module>/
├── domain/          entities, value objects, rules, events — pure Python
├── application/     use-case services (implement inbound ports)
├── ports/inbound/   use-case interfaces + DTOs (plain values only)
├── ports/outbound/  repositories and external services the module needs
└── infrastructure/  the Django app: models, migrations, api/ (DRF), persistence/, dependencies.py
```

Rules (1, 2, 3 and 5 enforced by import-linter contracts in `backend/pyproject.toml`):

1. Dependencies point inwards: infrastructure → application → ports → domain.
2. domain / ports / application never import django, rest_framework, celery, psycopg or redis.
3. Inner layers never import any `infrastructure` package.
4. Modules talk to each other **only through inbound ports** (e.g. `authentication` uses
   `user_accounts.ports.inbound.account_access.AccountAccess`). Never read another module's tables.
5. Use cases receive and return DTOs, never entities. REST adapters import ports, never a domain.

Modules: `shared_kernel`, `authentication`, `user_accounts`, `products`, `customers`, `chatbot`,
`quotations`, `work_orders`, `accounting_export`, `backups`, `price_history`. Names follow the
architecture diagram (+ `price_history`, new).

### Module template

`products` is the reference implementation (see `backend/README.md`, "Module template"). Every use
case: `actor.require(Permission.X)` → domain → repository → `AuditLogger` → output DTO. Tests in
`backend/tests/<module>/`: domain (no DB), use cases with in-memory fakes, API with real sessions
(`logged_in_client(RoleType.X)` fixture in `tests/conftest.py`).

### Cross-cutting decisions

- **Errors:** raise shared kernel errors (`ValidationError` 400, `AuthenticationError` 401,
  `PermissionDeniedError` 403, `NotFoundError` 404, `ConflictError` 409). API error body:
  `{"detail", "errors": {field: [...]}, "code"?}`. Messages in Spanish.
- **Transactions:** one per request (`ATOMIC_REQUESTS`). Failures that must be persisted (failed
  logins, lockout counter, their audit) are **returned as `Outcome` errors**, not raised, and the
  view uses `error_response()`; raising would roll them back.
- **Audit:** `DatabaseAuditLogger` writes to `audit_entry`, insert-only: PostgreSQL triggers
  reject UPDATE / DELETE (row, `0002`) and TRUNCATE (statement, `0004`), so `manage.py flush` and
  `transaction=True` tests cannot work (use the default transactional rollback tests). The
  triggers do not stop the table owner (see pending items). Never include passwords/hashes.
  `actor_type` USER / SYSTEM / ANONYMOUS: a failed login on an **existing** account records that
  account as actor (USER = "the account involved", not proof that its owner acted); only an
  unknown email is ANONYMOUS (as in the corrections README).
- **Text rules:** names use `shared_kernel.domain.text.clean_text` (collapses spaces, collects
  errors); free text with line breaks (terms, reasons) uses quotations' `clean_multiline_text`.
- **Events (Observer):** `shared_kernel` in-process `event_bus`; subscribe in `AppConfig.ready()`.
- **Emails:** `Notifier` port → Celery after commit (`on_commit(robust=True)`); Mailpit in dev.
- **Roles:** fixed (SUPERADMIN, ADMIN, OPERATOR); matrix in `shared_kernel/domain/security.py`;
  stored as a column of `app_user` (no ROLE tables). SUPERADMIN and ADMIN share permissions.
- **Pagination:** server-side, max 50 per page (`PageRequest`), envelope
  `{count, page, page_size, total_pages, results}`.
- **Authentication:** PyJWT behind `TokenIssuer` (not SimpleJWT). Login = password → pre-auth token
  → TOTP enrollment (QR, 5 min) or 6-digit verification. Access token 5 min (kept in browser
  memory), refresh token in an httpOnly SameSite=Strict cookie on `/api/auth/`, rotated on use
  (reuse closes the session). Session writes go through three intent methods of
  `SessionRepository` (`record_activity`, `rotate_refresh_token`, `record_termination`), each a
  single conditional UPDATE of its own columns **and only while the row is ACTIVE**: a late write
  never reopens a closed session (audit F-01/F-02) nor undoes another request's rotation, and the
  first closing reason wins (the second termination writes nothing and is not audited). Never
  add a generic "save the whole session" method. A tab that loses a rotation race gets 409
  `REFRESH_CONFLICT`, the cookie is **not** cleared (it is shared by all tabs) and the client
  retries once; tabs also serialize refreshes with the Web Locks API. If the session was closed
  meanwhile, the refresh answers its closing reason instead. Every request checks the `session`
  row: single session, 15-minute inactivity, deactivated account; the role is read from the
  account on each request. Lockout: 3 failures (password, verification code or enrollment code)
  → 15 minutes, enforced in every step (login, enrollment start/confirm, verify): while locked
  even the right code is refused. **Unknown emails** follow the same counter and lock
  (`UnknownEmailAttempts`, kept in the cache under an HMAC of the email, never the address), so
  answers never reveal which emails exist (audit F-03a). Accepted trade-off (F-03b): anyone can
  lock a known account for 15 minutes; mitigated by the per-IP limits and the manual unlock.
  **Rate limits per IP** (audit F-04): `auth_login` 10/min, `auth_code` 20/min (enrollment and
  verify), `auth_refresh` 60/min; 429 answers `code: RATE_LIMITED` with a Spanish message and a
  `Retry-After` header. `auth_refresh` counts page loads/reloads, new tabs and the 5-minute token
  renewal of each tab, shared by everyone behind the same IP (not SPA navigation). A refresh 429
  is **never a logout** (the session is still open): on page load the loading screen shows
  "Demasiadas solicitudes desde esta conexión. Reintentando en N segundos…" and retries after
  `Retry-After` (up to 3 times, then /login with the message); inside the app the request that
  needed the token fails with the server's message (`renewAfter401` in `http.ts`). The
  pre-auth token is a stateless JWT (several attempts allowed until it expires). TOTP secrets
  encrypted with Fernet.
- **Client IP:** `client_ip()` uses DRF's `get_ident` (the same as the rate limits): behind
  `NUM_PROXIES` trusted proxies it reads `X-Forwarded-For`, with 0 it ignores that header. Set
  `NUM_PROXIES` to the real number of reverse proxies in production, never higher.
- **Tests:** an autouse fixture clears the cache before and after each test (rate-limit counters
  and unknown-email locks live there).
- **State transitions** are `POST` actions (`/activate/`, `/deactivate/`, later `/approve/`…).
- **Customers:** abstract `Customer` with `NaturalPerson` / `LegalEntity` (factory
  `Customer.register`). NIT validated with the DIAN check digit; natural ID 5–15 digits; tax id and
  type immutable; inactive customers are read-only and can be reactivated. Profile route
  `/clientes/:taxId` (API `/api/customers/by-tax-id/<tax_id>/` accepts any common format).
  Commercial notes: only the author edits, anyone with `CUSTOMER_MANAGE` deletes (text kept in the
  audit log); the author's name is a snapshot taken from `Actor.display_name`.
- **Frontend:** `shared/api/http.ts` adds the Bearer token, refreshes once on 401 (single-flight)
  and sends the user to `/login` with the reason. Permissions from `useSession().user`
  (`hasPermission`) only hide UI; the backend enforces them.
- **Quotations (4a):** public portal `/cotizar` (3 steps, no account) → `/api/chatbot/…` (public,
  rate-limited per IP with DRF `ScopedRateThrottle`; `NUM_PROXIES` controls the client IP). The
  `chatbot` module is the public adapter; it calls the `quotations.QuotationRequests` and
  `products.ProductCatalog` inbound ports. Prices are `PriceRange` (whole COP, `Decimal`); a line
  without history is `None` = "Precio por confirmar" (user decision). Estimator =
  `FallbackPriceEstimator` (see AI features below), statistical = interquartile range of APPROVED
  final unit prices in the last 365 days. Dispatch date = `NoHistoryDispatchDateEstimator`
  until step 5. Quotation numbers `COT-<year>-<0001>` (locked sequence row). Validity 15 days.
  Data-processing consent (Law 1581) required. PDFs with ReportLab (escape user text). The
  requester gets an `access_key` to download/email only their quotation: it always travels in the
  request body (PDF and email are `POST`), never in the URL (logs, history), and is compared as
  bytes with `compare_digest` (any key → same 404). Institution and NIT are
  optional fields (to suggest linking a customer in 4b).
- **Quotation review (4b):** `QuotationReview` inbound port (`QUOTATION_MANAGE`, Operador denied)
  under `/api/quotations/` (list with filters, detail, `/modify/`, `/approve/`, `/reject/`,
  `/customer/`, `/pdf/`). Modify (→ MODIFIED) requires a reason (audited); approve requires a final
  unit price per item and a dispatch date ≥ today, stores `final_total`/`approved_at`/`approved_by`,
  restarts the 15-day validity, emails the formal PDF and publishes `QuotationApproved` (no
  subscribers until step 5); reject requires a reason and emails it. APPROVED/REJECTED are
  immutable (`QuotationLocked`, 409); the only later change is linking a customer to an approved
  quotation without one. Customers are reached through the new `customers.CustomerDirectory`
  inbound port (suggestion when the requester's NIT matches an active customer, with or without
  check digit). The 360 history uses `quotations.CustomerQuotations` (`QuotationsCommercialHistory`
  adapter). The two composition roots import each other lazily (inside the functions) to avoid an
  import cycle. Frontend: `/cotizaciones` tray and `/cotizaciones/:id` review; protected PDFs are
  downloaded with `downloadFile()` (Bearer token + blob).
- **AI provider (4c):** OpenRouter (OpenAI-compatible) configured by `LLM_BASE_URL`, `LLM_API_KEY`,
  `LLM_MODEL` in `.env` (default `google/gemma-4-31b-it:free`: in November 2026 OpenRouter had no
  free DeepSeek model; `deepseek/deepseek-v4.1-flash` is a cheap paid option). Switching provider
  or model = changing env vars. Shared kernel port `LanguageModel.complete_json()` + adapter
  `OpenAICompatibleLanguageModel` (stdlib `urllib`, no extra dependency); tests force
  `LLM_API_KEY=""` and never call a real provider. It sends its own `User-Agent` (Cloudflare
  blocks `Python-urllib`, error 1010) and logs the provider's error message, never the key.
  `LLM_SESSION_HEADER` (optional) sends a new `ses_<random>` id per call for providers that
  require it. **OpenCode Go** (team subscription, owned by Carlos Cuervo): base URL
  `https://opencode.ai/inference/go/openai/v1`, model `deepseek-v4.1-flash`,
  `LLM_SESSION_HEADER=x-opencode-session`; **development and course demo only**: Go is designed
  for coding agents and the OpenCode Terms limit the services to internal use, not for the benefit
  of third parties. **Production** must use a pay-as-you-go API instead (OpenCode Zen:
  `https://opencode.ai/inference/openai/v1`, same model id, no session header; or OpenRouter).
- **AI features (4c):** (1) **free text → proposal** (US 2.41): `ItemProposer` sends the active
  catalog + the description with emails / long numbers removed (`strip_personal_data`), keeps only
  real catalog codes, nothing is added until the requester confirms, the text is not stored;
  `/api/chatbot/assistant/` says whether the option is on, `/api/chatbot/proposal/` (throttle
  `public_proposal`, 503 `AI_UNAVAILABLE` when it fails). (2) **AI price estimate**: the chain is
  `FallbackPriceEstimator([StatisticalPriceEstimator, CachedPriceEstimator(AiPriceEstimator)])`:
  the product's own history first; the AI only fills gaps, in ONE batch call, using recent approved
  prices of other products as references. An AI range is discarded unless it cites real reference
  codes and stays within ×4 of their prices; no references → no call ("Precio por confirmar").
  Results (including "no estimate") are cached per product in Redis for `AI_PRICE_CACHE_SECONDS`.
  Each item stores `price_source` (HISTORY / AI), shown to the requester ("Estimado con IA") and
  in the review. Personal data is never sent to the AI.
- Patterns required by NFR-05-01: Factory (`Entity.register`), Singleton (`lru_cache`
  composition roots, `event_bus`), Observer (events), Strategy (price estimators, dispatch-date
  estimator).

## Roadmap (implementation order chosen by the user: option D)

| # | Step | Status |
|---|---|---|
| 0 | Documentation corrections | Done |
| 1 | Skeleton, Docker, Products (template) | Done |
| 2 | Authentication + user accounts + audit (backend and frontend) | Done |
| 3 | Customers and commercial notes | Done |
| 4 | Chatbot (hybrid assistant) + Quotations | Done (4a public assistant, 4b admin review, 4c AI: free text + AI price estimate) |
| 5 | Siigo export queue + Work orders | Pending |
| 6 | Backups + WhatsApp price history import | Pending |

The first push/PR happens when the user decides (first release with several modules working).

## Pending items — remind the user at the right time

- **Sandbox restore adapter** (isolated environment for backup tests, FR-01-09): before step 6.
- **Siigo Pyme flat-file format** (columns, CSV/TXT): ask the user before implementing the export.
- **Postman collection** (can be imported from `/api/schema/`): later.
- **WhatsApp screenshots**: confirm whether the AI provider can read images (else OCR or `.txt`);
  the WhatsApp samples should also feed `PriceHistory.reference_samples` (AI price references).
- **AI in production**: verified in Docker with OpenCode Go (development only); switch to a
  pay-as-you-go provider (OpenCode Zen or OpenRouter) before any real deployment.
- Dashboard, weekly report and audit-log screens: define during development.
- **Production settings module** (`config/settings/prod.py`, before any real deployment; audit
  N-01…N-03): refuse to start without `JWT_SIGNING_KEY` and `TOTP_ENCRYPTION_KEY` (today both are
  silently derived from `SECRET_KEY`), `DEBUG=False`, `REFRESH_COOKIE_SECURE=True`, hide
  `/api/docs/`, `/api/redoc/` and `/api/schema/`, and make the entrypoints (`manage.py`,
  `wsgi.py`, `asgi.py`, `celery.py`) not default to `dev` there. Also cap the login password at
  72 bytes (bcrypt limit; the policy already does it for new passwords).
- Security audit record: `docs/security-audit-2026-11-26.md` (Carlos Cuervo); keep its status
  table updated when an item is fixed.
- **Database roles (before any real deployment):** today Django connects as `imsi`, owner and
  superuser, who can disable the audit triggers. Split into an owner role used only by `migrate`
  and an application role (backend, worker, beat) that does not own the tables and has only
  `SELECT, INSERT` on `audit_entry` (no UPDATE / DELETE / TRUNCATE / ALTER). Migration `0003`
  (`REVOKE … FROM PUBLIC`) is harmless but does not provide this.
- Audit-log screen: a `LOGIN_FAILED` / `ACCOUNT_LOCKED` row with a USER actor means "this account
  was targeted", not that its owner acted; make that clear in the UI.
- Frontend bundle > 500 kB: split by route later.
- **Customer history** on the 360 profile lists quotations (`QuotationsCommercialHistory`); merge
  work orders into it in step 5. Step 5 also subscribes to `QuotationApproved` (export queue).

## Environment notes

- Windows host; Docker Desktop with WSL 2. The repo path contains spaces and accents.
- Inside Docker, `.env` sets `DJANGO_SETTINGS_MODULE=config.settings.dev`; pytest overrides it.
- Raw SQL in migrations: avoid `%` (psycopg placeholder) or pass `params=None`.
