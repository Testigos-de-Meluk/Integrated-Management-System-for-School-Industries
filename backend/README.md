# IMSI Backend

Django + Django REST Framework + Celery, organized as a **modular monolith** where **every module
follows the hexagonal architecture** (ports and adapters).

## Layout

```
backend/
├── config/                     # Django project: settings, root URLs, WSGI/ASGI, Celery app
│   └── settings/               # base.py (shared), dev.py (Docker Compose), test.py (pytest)
├── modules/                    # One package per business module
│   └── <module>/
│       ├── domain/             # Entities, value objects, domain services, events. Pure Python.
│       ├── application/        # Use-case services: implement inbound ports, use outbound ports.
│       ├── ports/
│       │   ├── inbound/        # Use-case interfaces (what the outside world can ask for)
│       │   └── outbound/       # Repositories, notifiers, external services (what the app needs)
│       └── infrastructure/     # Adapters. This package IS the Django app of the module.
│           ├── apps.py         # AppConfig (label = module name)
│           ├── models.py       # Django ORM models (persistence detail, never leave this layer)
│           ├── migrations/
│           ├── api/            # Inbound REST adapters: views, serializers (DTOs), urls.py
│           └── persistence/    # Outbound adapters: repositories and entity <-> model mappers
├── tests/                      # pytest suite (synthetic data only, NFR-05-02)
├── requirements/               # base.txt (runtime), dev.txt (tests and linters)
└── pyproject.toml              # ruff, pytest, coverage and import-linter configuration
```

## Modules

| Module | URL prefix | Responsibility | Status |
|---|---|---|---|
| `shared_kernel` | — | Common value objects (Money, PriceRange…), audit log, notifications, file storage, pagination, health check | Done |
| `authentication` | `/api/auth/` | Login, TOTP 2FA, single active session, inactivity timeout, temporary lockout | Done |
| `user_accounts` | `/api/users/` | User CRUD, fixed roles and permissions (RBAC) | Done |
| `products` | `/api/products/` | Product catalog (no official prices) | Done |
| `customers` | `/api/customers/` | Natural persons / legal entities, 360° profile, commercial notes | Done |
| `chatbot` | `/api/chatbot/` | Hybrid virtual assistant (guided steps + free-text proposals) | Done |
| `quotations` | `/api/quotations/` | Price-range estimation, PDF, review, approval, rejection | Done |
| `work_orders` | `/api/work-orders/` | O.T. generation from approved quotations and status lifecycle | Done (5a) |
| `accounting_export` | `/api/accounting-export/` | Processing queue and Siigo Pyme 10.1 flat-file batches | Skeleton |
| `backups` | `/api/backups/` | Scheduled full/differential backups, inventory, verified restore | Skeleton |
| `price_history` | `/api/price-history/` | WhatsApp chat import and review of price samples | Skeleton |

A *Skeleton* module only has its package layout, permission and empty `urlpatterns`: it has no
endpoint yet. `chatbot` exposes the public side of the assistant; the admin review of quotations
lives in `quotations`.

## Architecture rules

1. **Dependencies point inwards:** `infrastructure → application → ports → domain`. Never the reverse.
2. **`domain`, `ports` and `application` are framework-free:** no `django`, `rest_framework`, `celery`,
   `psycopg` or `redis` imports.
3. **ORM models never leave `infrastructure`.** Repositories map them to domain entities; REST views
   return serializers (DTOs), never entities or models.
4. **Modules talk to each other through inbound ports** (use-case interfaces), not by reaching into
   another module's models or repositories.
5. **Domain entities never cross the inbound port.** Use cases receive input DTOs and return output
   DTOs (e.g. `ProductView`); REST adapters (`infrastructure/api/`) import ports, never a domain.

Rules 1, 2 and 5 (plus "inner layers never import infrastructure") are checked automatically by
[import-linter](https://import-linter.readthedocs.io/). See the contracts in `pyproject.toml`.

## Module template: `products`

`products` is the **reference implementation**. Copy its structure when building a new module:

| Layer | File | What it contains |
|---|---|---|
| domain | `domain/product.py` | Aggregate with its invariants and a factory method (`Product.register`). Pure Python. |
| domain | `domain/exceptions.py` | Business errors extending the shared kernel ones (`ValidationError`, `NotFoundError`, `ConflictError`). Messages in Spanish. |
| ports | `ports/inbound/product_use_cases.py` | Use-case interface + DTOs: input (`RegisterProductCommand`, `UpdateProductCommand`, `ProductFilters`) and output (`ProductView`). Plain values only. |
| ports | `ports/outbound/product_repository.py` | Repository interface. |
| application | `application/product_service.py` | Implements the inbound port: checks permissions (`actor.require(...)`), calls the domain, saves through the repository, writes the audit record and returns a `ProductView` (`to_view`), never the entity. |
| infrastructure | `models.py` + `migrations/` | Django ORM model (persistence only). |
| infrastructure | `persistence/mappers.py`, `persistence/django_product_repository.py` | Entity ↔ model mapping and the repository adapter. |
| infrastructure | `api/serializers.py`, `api/views.py`, `api/urls.py` | DTOs, thin REST controllers documented with `@extend_schema`, routes. |
| infrastructure | `dependencies.py` | Composition root: the only place that chooses which adapter implements each port. |

Tests follow the same split (`tests/products/`): domain tests (no database), use-case tests with
in-memory fakes (`fakes.py`, no database), and API tests marked `django_db`.

### Shared kernel pieces every module uses

- `shared_kernel.domain.security`: `Actor`, `RoleType`, `Permission` and the fixed role-permission matrix.
- `shared_kernel.domain.pagination`: `PageRequest` (max 50) and `Page`.
- `shared_kernel.domain.audit` + `ports.outbound.audit_logger`: audit records and the `AuditLogger`
  port, implemented by `DatabaseAuditLogger` on the insert-only `audit_entry` table (a PostgreSQL
  trigger rejects every UPDATE and DELETE, NFR-08-01).
- `shared_kernel.domain.events` + `ports.outbound.event_publisher`: domain events and the
  in-process event bus (**Observer** pattern). Modules subscribe in their `AppConfig.ready()`.
- `shared_kernel.ports.outbound.notifier`: emails, sent by Celery after the transaction commits
  (`CeleryEmailNotifier`). In development they arrive in Mailpit.
- `shared_kernel.ports.outbound.password_hasher`: bcrypt, cost 12 (`BcryptPasswordHasher`).
- `shared_kernel.infrastructure.api`: `get_current_actor`, the error handler (single error format
  `{"detail", "errors"}`) and pagination helpers.

Every API request runs inside one database transaction (`ATOMIC_REQUESTS`, NFR-04-02): if any step
fails — a business rule, the audit entry — nothing is saved.

### Authentication (how a request is authenticated)

1. `POST /api/auth/login/` (email + password) → short-lived **pre-authentication token**.
2. First login: `POST /api/auth/enrollment/` (QR + secret, valid 5 min) and
   `POST /api/auth/enrollment/confirm/` (code). Other logins: `POST /api/auth/verify/` (6-digit code).
3. The response contains the **access token** (5 min, kept in memory by the frontend) and sets the
   **refresh token** as an `httpOnly` cookie limited to `/api/auth/`.
4. Every request sends `Authorization: Bearer <access token>`. `SessionJwtAuthentication` checks the
   token **and** its row in the `session` table (single session, 15-minute inactivity, deactivated
   account) and reads the role from the account, so role changes apply immediately.
5. `POST /api/auth/refresh/` renews the access token and rotates the refresh cookie; replaying an old
   refresh token closes the session (theft detection).

Failed logins must be **saved** (lockout counter and audit) even though the request fails, so those
use cases return an `Outcome` with the error instead of raising it (raising would roll back the
request's transaction). In Swagger UI, use **Authorize** with the access token.

**Production keys** (never commit them): `JWT_SIGNING_KEY` (long random string) and
`TOTP_ENCRYPTION_KEY` (Fernet key: `python -c "from cryptography.fernet import Fernet;
print(Fernet.generate_key().decode())"`). Empty values are only acceptable in development.

### First Superadministrador

Only administrators can create accounts, so the first one is created from the command line. The
initial password is generated and printed once:

```bash
docker compose exec backend python manage.py create_superadmin --email admin@empresa.com --name "Carlos Ríos"
```

Lost a password, or nobody can log in? Passwords are bcrypt hashes and can never be read back, but
they can be replaced (also unlocks the account and closes its sessions; add
`--reset-authenticator` if the phone with the authenticator app was lost):

```bash
docker compose exec backend python manage.py reset_password --email admin@empresa.com
```

## Common commands

Run them inside the backend container (the project must be running with `docker compose up`):

```bash
docker compose exec backend pytest                    # tests
docker compose exec backend pytest --cov              # tests + coverage
docker compose exec backend ruff check .              # lint
docker compose exec backend ruff format .             # format
docker compose exec backend lint-imports              # architecture rules
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate
```
