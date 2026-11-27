"""Root URL configuration. Each module exposes its REST routes from its infrastructure layer."""

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from modules.shared_kernel.infrastructure.api.views import health, holidays

MODULE_ROUTES = {
    "auth": "authentication",
    "users": "user_accounts",
    "products": "products",
    "customers": "customers",
    "chatbot": "chatbot",
    "quotations": "quotations",
    "work-orders": "work_orders",
    "accounting-export": "accounting_export",
    "backups": "backups",
    "price-history": "price_history",
}

urlpatterns = [
    path("api/health/", health, name="health"),
    path("api/calendar/holidays/", holidays, name="holidays"),
    # API documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    *[
        path(f"api/{prefix}/", include(f"modules.{module}.infrastructure.api.urls"))
        for prefix, module in MODULE_ROUTES.items()
    ],
]
