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
- **Audit:** `DatabaseAuditLogger` writes to `audit_entry`, insert-only (PostgreSQL trigger).
  Never include passwords/hashes. `actor_type` USER / SYSTEM / ANONYMOUS.
- **Events (Observer):** `shared_kernel` in-process `event_bus`; subscribe in `AppConfig.ready()`.
- **Emails:** `Notifier` port → Celery after commit (`on_commit(robust=True)`); Mailpit in dev.
- **Roles:** fixed (SUPERADMIN, ADMIN, OPERATOR); matrix in `shared_kernel/domain/security.py`;
  stored as a column of `app_user` (no ROLE tables). SUPERADMIN and ADMIN share permissions.
- **Pagination:** server-side, max 50 per page (`PageRequest`), envelope
  `{count, page, page_size, total_pages, results}`.
- **Authentication:** PyJWT behind `TokenIssuer` (not SimpleJWT). Login = password → pre-auth token
  → TOTP enrollment (QR, 5 min) or 6-digit verification. Access token 5 min (kept in browser
  memory), refresh token in an httpOnly SameSite=Strict cookie on `/api/auth/`, rotated on use
  (reuse closes the session). Every request checks the `session` row: single session, 15-minute
  inactivity, deactivated account; the role is read from the account on each request. Lockout:
  3 failures (password or code) → 15 minutes. TOTP secrets encrypted with Fernet.
- **State transitions** are `POST` actions (`/activate/`, `/deactivate/`, later `/approve/`…).
- **Frontend:** `shared/api/http.ts` adds the Bearer token, refreshes once on 401 (single-flight)
  and sends the user to `/login` with the reason. Permissions from `useSession().user`
  (`hasPermission`) only hide UI; the backend enforces them.
- Patterns required by NFR-05-01: Factory (`Entity.register`), Singleton (`lru_cache`
  composition roots, `event_bus`), Observer (events), Strategy (pending: price/dispatch estimators).

## Roadmap (implementation order chosen by the user: option D)

| # | Step | Status |
|---|---|---|
| 0 | Documentation corrections | Done |
| 1 | Skeleton, Docker, Products (template) | Done |
| 2 | Authentication + user accounts + audit (backend and frontend) | Done |
| 3 | Customers and commercial notes | **Next** |
| 4 | Chatbot (hybrid assistant) + Quotations | Pending |
| 5 | Siigo export queue + Work orders | Pending |
| 6 | Backups + WhatsApp price history import | Pending |

The first push/PR happens when the user decides (first release with several modules working).

## Pending items — remind the user at the right time

- **Sandbox restore adapter** (isolated environment for backup tests, FR-01-09): before step 6.
- **Siigo Pyme flat-file format** (columns, CSV/TXT): ask the user before implementing the export.
- **Postman collection** (can be imported from `/api/schema/`): later.
- **WhatsApp screenshots**: confirm whether the AI provider can read images (else OCR or `.txt`).
- Dashboard, weekly report and audit-log screens: define during development.
- Production keys `JWT_SIGNING_KEY`, `TOTP_ENCRYPTION_KEY`: required before any real deployment.
- Frontend bundle > 500 kB: split by route later.

## Environment notes

- Windows host; Docker Desktop with WSL 2. The repo path contains spaces and accents.
- Inside Docker, `.env` sets `DJANGO_SETTINGS_MODULE=config.settings.dev`; pytest overrides it.
- Raw SQL in migrations: avoid `%` (psycopg placeholder) or pass `params=None`.
