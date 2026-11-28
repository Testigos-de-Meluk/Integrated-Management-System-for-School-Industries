/** Data layer of the work orders (/api/work-orders/): Operador, Administrador, Superadministrador. */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Paginated } from "@/shared/api/http";

export type WorkOrderStatus = "PENDING" | "REGISTERED_IN_SIIGO" | "RECONCILED" | "CANCELLED";

export const WORK_ORDER_STATUS_LABELS: Record<WorkOrderStatus, string> = {
  PENDING: "Pendiente",
  REGISTERED_IN_SIIGO: "Registrada en Siigo",
  RECONCILED: "Conciliada",
  CANCELLED: "Anulada",
};

export const WORK_ORDER_STATUS_STYLES: Record<WorkOrderStatus, string> = {
  PENDING: "bg-amber-50 text-amber-800",
  REGISTERED_IN_SIIGO: "bg-sky-50 text-sky-800",
  RECONCILED: "bg-green-50 text-green-800",
  CANCELLED: "bg-slate-100 text-slate-600",
};

export type WorkOrderItem = {
  product_id: string;
  product_code: string;
  description: string;
  unit_of_measure: string;
  quantity: number;
};

export type WorkOrderSummary = {
  id: string;
  number: string;
  quotation_id: string;
  quotation_number: string;
  customer_id: string;
  customer_tax_id: string;
  customer_name: string;
  items: WorkOrderItem[];
  agreed_delivery_date: string;
  status: WorkOrderStatus;
  created_at: string;
};

export type WorkOrderDetail = WorkOrderSummary & {
  actual_dispatch_date: string | null;
  cancellation_reason: string;
  created_by_name: string;
  can_edit: boolean;
  can_reconcile: boolean;
  can_cancel: boolean;
  was_exported: boolean;
};

export type AvailableQuotation = {
  id: string;
  number: string;
  approved_at: string;
  requester_name: string;
  requester_institution: string;
  requester_tax_id: string;
  customer_id: string | null;
  customer_name: string | null;
  customer_active: boolean | null;
  dispatch_date: string | null;
  items: WorkOrderItem[];
};

export type WorkOrderFilters = {
  number?: string;
  quotation_number?: string;
  customer?: string;
  product?: string;
  agreed_from?: string;
  agreed_to?: string;
  status?: WorkOrderStatus | "";
};

export type GenerateInput = {
  quotation_id: string;
  customer_id: string | null;
  agreed_delivery_date: string | null;
};

export type UpdateInput = {
  customer_id: string;
  items: { product_id: string; quantity: number }[];
  agreed_delivery_date: string;
};

const keys = {
  all: ["work-orders"] as const,
  list: (filters: WorkOrderFilters, page: number) => [...keys.all, "list", { ...filters, page }] as const,
  detail: (id: string) => [...keys.all, "detail", id] as const,
  available: (search: string, page: number) => [...keys.all, "available", { search, page }] as const,
};

export function useWorkOrders(filters: WorkOrderFilters, page: number, pageSize = 20) {
  return useQuery({
    queryKey: keys.list(filters, page),
    queryFn: () =>
      api.get<Paginated<WorkOrderSummary>>("/work-orders/", { ...filters, page, page_size: pageSize }),
    placeholderData: keepPreviousData,
  });
}

export function useWorkOrder(id: string) {
  return useQuery({
    queryKey: keys.detail(id),
    queryFn: () => api.get<WorkOrderDetail>(`/work-orders/${id}/`),
    enabled: Boolean(id),
  });
}

export function useAvailableQuotations(search: string, page: number, enabled: boolean) {
  return useQuery({
    queryKey: keys.available(search, page),
    queryFn: () =>
      api.get<Paginated<AvailableQuotation>>("/work-orders/available-quotations/", {
        search,
        page,
        page_size: 10,
      }),
    placeholderData: keepPreviousData,
    enabled,
  });
}

function useWorkOrderMutation<TInput>(request: (input: TInput) => Promise<WorkOrderDetail>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: request,
    onSuccess: (order) => {
      queryClient.setQueryData(keys.detail(order.id), order);
      void queryClient.invalidateQueries({ queryKey: keys.all });
      // The quotation may have got its customer linked; the 360 history lists quotations.
      void queryClient.invalidateQueries({ queryKey: ["quotations"] });
      void queryClient.invalidateQueries({ queryKey: ["customers"] });
      void queryClient.invalidateQueries({ queryKey: ["export-queue"] }); // generated / annulled
    },
  });
}

export function useGenerateWorkOrder() {
  return useWorkOrderMutation((input: GenerateInput) => api.post<WorkOrderDetail>("/work-orders/", input));
}

export function useUpdateWorkOrder(id: string) {
  return useWorkOrderMutation((input: UpdateInput) =>
    api.patch<WorkOrderDetail>(`/work-orders/${id}/`, input),
  );
}

export function useCancelWorkOrder(id: string) {
  return useWorkOrderMutation((reason: string) =>
    api.post<WorkOrderDetail>(`/work-orders/${id}/cancel/`, { reason }),
  );
}

export function useReconcileWorkOrder(id: string) {
  return useWorkOrderMutation((actualDispatchDate: string) =>
    api.post<WorkOrderDetail>(`/work-orders/${id}/reconcile/`, {
      actual_dispatch_date: actualDispatchDate,
    }),
  );
}
