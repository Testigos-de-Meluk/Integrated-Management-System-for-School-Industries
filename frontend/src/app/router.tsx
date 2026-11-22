import { createBrowserRouter } from "react-router";

import { AppLayout } from "@/app/AppLayout";
import { RequireAuth, RequirePermission } from "@/app/guards";
import { LoginPage } from "@/features/auth/LoginPage";
import { CustomerProfilePage } from "@/features/customers/CustomerProfilePage";
import { CustomersPage } from "@/features/customers/CustomersPage";
import { ProductsPage } from "@/features/products/ProductsPage";
import { QuoteRequestPage } from "@/features/quote-request/QuoteRequestPage";
import { UsersPage } from "@/features/users/UsersPage";
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
