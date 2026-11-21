/** Data layer of the product catalog: API types and TanStack Query hooks. */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Paginated } from "@/shared/api/http";

export type ProductStatus = "ACTIVE" | "INACTIVE";

export const STATUS_LABELS: Record<ProductStatus, string> = {
  ACTIVE: "Activo",
  INACTIVE: "Inactivo",
};

export type Product = {
  id: string;
  code: string;
  name: string;
  unit_of_measure: string;
  status: ProductStatus;
};

export type ProductFilters = {
  code?: string;
  name?: string;
  unit_of_measure?: string;
  status?: ProductStatus | "";
};

export type ProductInput = { code: string; name: string; unit_of_measure: string };

const productKeys = {
  all: ["products"] as const,
  list: (filters: ProductFilters, page: number, pageSize: number) =>
    [...productKeys.all, "list", { ...filters, page, pageSize }] as const,
};

export function useProducts(filters: ProductFilters, page: number, pageSize = 20) {
  return useQuery({
    queryKey: productKeys.list(filters, page, pageSize),
    queryFn: () =>
      api.get<Paginated<Product>>("/products/", { ...filters, page, page_size: pageSize }),
    placeholderData: keepPreviousData, // keeps the table visible while the next page loads
  });
}

function useInvalidateProducts() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: productKeys.all });
}

export function useCreateProduct() {
  const invalidate = useInvalidateProducts();
  return useMutation({
    mutationFn: (input: ProductInput) => api.post<Product>("/products/", input),
    onSuccess: invalidate,
  });
}

export function useUpdateProduct() {
  const invalidate = useInvalidateProducts();
  return useMutation({
    mutationFn: ({ id, ...input }: Omit<ProductInput, "code"> & { id: string }) =>
      api.patch<Product>(`/products/${id}/`, input),
    onSuccess: invalidate,
  });
}

export function useChangeProductStatus() {
  const invalidate = useInvalidateProducts();
  return useMutation({
    mutationFn: ({ id, activate }: { id: string; activate: boolean }) =>
      api.post<Product>(`/products/${id}/${activate ? "activate" : "deactivate"}/`),
    onSuccess: invalidate,
  });
}
