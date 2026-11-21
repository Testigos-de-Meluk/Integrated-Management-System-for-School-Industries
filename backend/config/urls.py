"""Root URL configuration. Each module exposes its REST routes from its infrastructure layer."""

from django.urls import include, path

from modules.shared_kernel.infrastructure.api.views import health

MODULE_ROUTES = {
    "auth": "authentication",
    "users": "user_accounts",
    "catalog": "catalog",
    "customers": "customers",
    "assistant": "assistant",
    "quotations": "quotations",
    "work-orders": "work_orders",
    "accounting-export": "accounting_export",
    "backups": "backups",
    "price-history": "price_history",
}

urlpatterns = [
    path("api/health/", health, name="health"),
    *[
        path(f"api/{prefix}/", include(f"modules.{module}.infrastructure.api.urls"))
        for prefix, module in MODULE_ROUTES.items()
    ],
]
