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

| Module | URL prefix | Responsibility |
|---|---|---|
| `shared_kernel` | — | Common value objects (Money, PriceRange…), audit log, notifications, file storage, pagination, health check |
| `authentication` | `/api/auth/` | Login, TOTP 2FA, single active session, inactivity timeout, temporary lockout |
| `user_accounts` | `/api/users/` | User CRUD, fixed roles and permissions (RBAC) |
| `catalog` | `/api/catalog/` | Products (no official prices) |
| `customers` | `/api/customers/` | Natural persons / legal entities, 360° profile, commercial notes |
| `assistant` | `/api/assistant/` | Hybrid virtual assistant (guided steps + free-text proposals) |
| `quotations` | `/api/quotations/` | Price-range estimation, PDF, review, approval, rejection |
| `work_orders` | `/api/work-orders/` | O.T. generation from approved quotations and status lifecycle |
| `accounting_export` | `/api/accounting-export/` | Processing queue and Siigo Pyme flat-file batches |
| `backups` | `/api/backups/` | Scheduled full/differential backups, inventory, verified restore |
| `price_history` | `/api/price-history/` | WhatsApp chat import and review of price samples |

## Architecture rules

1. **Dependencies point inwards:** `infrastructure → application → ports → domain`. Never the reverse.
2. **`domain`, `ports` and `application` are framework-free:** no `django`, `rest_framework`, `celery`,
   `psycopg` or `redis` imports.
3. **ORM models never leave `infrastructure`.** Repositories map them to domain entities; REST views
   return serializers (DTOs), never entities or models.
4. **Modules talk to each other through inbound ports** (use-case interfaces), not by reaching into
   another module's models or repositories.

Rules 1 and 2 (and "inner layers never import infrastructure") are checked automatically by
[import-linter](https://import-linter.readthedocs.io/). See the contracts in `pyproject.toml`.

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
