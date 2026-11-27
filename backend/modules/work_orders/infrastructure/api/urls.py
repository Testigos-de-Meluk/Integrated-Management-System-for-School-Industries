"""REST routes of the Work Orders module, mounted at /api/work-orders/."""

from django.urls import path

from .views import (
    AvailableQuotationsView,
    WorkOrderCancelView,
    WorkOrderDetailView,
    WorkOrderListCreateView,
    WorkOrderReconcileView,
)

urlpatterns = [
    path("", WorkOrderListCreateView.as_view(), name="work-order-list"),
    path(
        "available-quotations/",
        AvailableQuotationsView.as_view(),
        name="work-order-available-quotations",
    ),
    path("<uuid:work_order_id>/", WorkOrderDetailView.as_view(), name="work-order-detail"),
    path("<uuid:work_order_id>/cancel/", WorkOrderCancelView.as_view(), name="work-order-cancel"),
    path(
        "<uuid:work_order_id>/reconcile/",
        WorkOrderReconcileView.as_view(),
        name="work-order-reconcile",
    ),
]
