import { createBrowserRouter } from "react-router";

import { AppLayout } from "@/app/AppLayout";
import { RequireAuth, RequirePermission } from "@/app/guards";
import { LoginPage } from "@/features/auth/LoginPage";
import { ProductsPage } from "@/features/products/ProductsPage";
import { UsersPage } from "@/features/users/UsersPage";
import { HomePage } from "@/pages/HomePage";
import { NotFoundPage } from "@/pages/NotFoundPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
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
