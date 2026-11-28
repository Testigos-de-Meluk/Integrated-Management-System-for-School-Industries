import { createBrowserRouter } from "react-router";

import { AppLayout } from "@/app/AppLayout";
import { RequireAuth, RequirePermission } from "@/app/guards";
import { LoginPage } from "@/features/auth/LoginPage";
import { ExportQueuePage } from "@/features/export-queue/ExportQueuePage";
import { CustomerProfilePage } from "@/features/customers/CustomerProfilePage";
import { CustomersPage } from "@/features/customers/CustomersPage";
import { ProductsPage } from "@/features/products/ProductsPage";
import { QuoteRequestPage } from "@/features/quote-request/QuoteRequestPage";
import { QuotationReviewPage } from "@/features/quotations/QuotationReviewPage";
import { QuotationsPage } from "@/features/quotations/QuotationsPage";
import { UsersPage } from "@/features/users/UsersPage";
import { WorkOrderDetailPage } from "@/features/work-orders/WorkOrderDetailPage";
import { WorkOrdersPage } from "@/features/work-orders/WorkOrdersPage";
import { HomePage } from "@/pages/HomePage";
import { NotFoundPage } from "@/pages/NotFoundPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  // Public portal for potential customers (no account).
  { path: "/cotizar", element: <QuoteRequestPage /> },
  {
    element: (
      <RequireAuth>
        <AppLayout />
      </RequireAuth>
    ),
    children: [
      { path: "/", element: <HomePage /> },
      {
        path: "/catalogo",
        element: (
          <RequirePermission permission="CATALOG_VIEW">
            <ProductsPage />
          </RequirePermission>
        ),
      },
      {
        path: "/clientes",
        element: (
          <RequirePermission permission="CUSTOMER_MANAGE">
            <CustomersPage />
          </RequirePermission>
        ),
      },
      {
        path: "/clientes/:taxId",
        element: (
          <RequirePermission permission="CUSTOMER_MANAGE">
            <CustomerProfilePage />
          </RequirePermission>
        ),
      },
      {
        path: "/cotizaciones",
        element: (
          <RequirePermission permission="QUOTATION_MANAGE">
            <QuotationsPage />
          </RequirePermission>
        ),
      },
      {
        path: "/cotizaciones/:quotationId",
        element: (
          <RequirePermission permission="QUOTATION_MANAGE">
            <QuotationReviewPage />
          </RequirePermission>
        ),
      },
      {
        path: "/ordenes-trabajo",
        element: (
          <RequirePermission permission="WORK_ORDER_MANAGE">
            <WorkOrdersPage />
          </RequirePermission>
        ),
      },
      {
        path: "/ordenes-trabajo/:workOrderId",
        element: (
          <RequirePermission permission="WORK_ORDER_MANAGE">
            <WorkOrderDetailPage />
          </RequirePermission>
        ),
      },
      {
        path: "/exportacion-odoo",
        element: (
          <RequirePermission permission="EXPORT_QUEUE_MANAGE">
            <ExportQueuePage />
          </RequirePermission>
        ),
      },
      {
        path: "/cuentas",
        element: (
          <RequirePermission permission="USER_MANAGE">
            <UsersPage />
          </RequirePermission>
        ),
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
