import { createBrowserRouter } from "react-router";

import { AppLayout } from "@/app/AppLayout";
import { ProductsPage } from "@/features/products/ProductsPage";
import { HomePage } from "@/pages/HomePage";
import { NotFoundPage } from "@/pages/NotFoundPage";

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: "/", element: <HomePage /> },
      { path: "/catalogo", element: <ProductsPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
