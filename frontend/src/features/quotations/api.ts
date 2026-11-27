/** Data layer of the quotation review (/api/quotations/, Administrador). */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, downloadFile, type Paginated } from "@/shared/api/http";

export type QuotationStatus = "PENDING_REVIEW" | "MODIFIED" | "APPROVED" | "REJECTED";

export const QUOTATION_STATUS_LABELS: Record<QuotationStatus, string> = {
  PENDING_REVIEW: "Pendiente de revisión",
  MODIFIED: "Modificada",
  APPROVED: "Aprobada",
  REJECTED: "Rechazada",
};

export const QUOTATION_STATUS_STYLES: Record<QuotationStatus, string> = {
  PENDING_REVIEW: "bg-amber-50 text-amber-800",
  MODIFIED: "bg-sky-50 text-sky-800",
  APPROVED: "bg-green-50 text-green-800",
  REJECTED: "bg-slate-100 text-slate-600",
};

export type QuotationSummary = {
  id: string;
  number: string;
  issued_at: string;
  status: QuotationStatus;
  requester_name: string;
  requester_email: string;
  requester_phone: string;
  requester_institution: string;
  products: string[];
  total_min: string | null;
  total_max: string | null;
  final_total: string | null;
  unpriced_items: number;
  has_customer: boolean;
};

export type ReviewItem = {
  id: string;
  product_id: string;
  product_code: string;
  description: string;
  unit_of_measure: string;
  quantity: number;
  unit_price_min: string | null;
  unit_price_max: string | null;
  subtotal_min: string | null;
  subtotal_max: string | null;
  final_unit_price: string | null;
  final_subtotal: string | null;
  price_source: "HISTORY" | "AI" | null;
};

export type LinkedCustomer = { id: string; tax_id: string; name: string; is_active: boolean };

export type QuotationDetail = {
  id: string;
  number: string;
  issued_at: string;
  valid_until: string;
  status: QuotationStatus;
  is_editable: boolean;
  requester_name: string;
  requester_email: string;
  requester_phone: string;
  requester_institution: string;
  requester_tax_id: string;
  items: ReviewItem[];
  total_min: string | null;
  total_max: string | null;
  final_total: string | null;
  unpriced_items: number;
  estimated_dispatch_date: string | null;
  dispatch_date_source: "SUGGESTED" | "MANUAL" | null;
  commercial_terms: string;
  rejection_reason: string;
  approved_at: string | null;
  approved_by_name: string;
  customer: LinkedCustomer | null;
  suggested_customer: LinkedCustomer | null;
  /** Median recalculated now (FR-02-06); null when not editable or without enough history. */
  suggested_dispatch_date: string | null;
};

export type QuotationFilters = {
  issued_from?: string;
  issued_to?: string;
  contact?: string;
  product?: string;
  total_min?: string;
  total_max?: string;
  status?: QuotationStatus | "";
};

export type ModifyInput = {
  items: { product_id: string; quantity: number; final_unit_price: string | null }[];
  reason: string;
  commercial_terms: string;
  dispatch_date: string | null;
};

export type ApproveInput = {
  prices: { item_id: string; final_unit_price: string | null }[];
  dispatch_date: string | null;
  commercial_terms: string;
};

const keys = {
  all: ["quotations"] as const,
  list: (filters: QuotationFilters, page: number) => [...keys.all, "list", { ...filters, page }] as const,
  detail: (id: string) => [...keys.all, "detail", id] as const,
};

export function useQuotations(filters: QuotationFilters, page: number, pageSize = 20) {
  return useQuery({
    queryKey: keys.list(filters, page),
    queryFn: () =>
      api.get<Paginated<QuotationSummary>>("/quotations/", { ...filters, page, page_size: pageSize }),
    placeholderData: keepPreviousData,
  });
}

export function useQuotation(id: string) {
  return useQuery({
    queryKey: keys.detail(id),
    queryFn: () => api.get<QuotationDetail>(`/quotations/${id}/`),
    retry: false,
  });
}

function useQuotationMutation<TInput>(request: (input: TInput) => Promise<QuotationDetail>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: request,
    onSuccess: (detail) => {
      queryClient.setQueryData(keys.detail(detail.id), detail);
      void queryClient.invalidateQueries({ queryKey: [...keys.all, "list"] });
      // The customer 360 profile lists its quotations.
      void queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
  });
}

export const useModifyQuotation = (id: string) =>
  useQuotationMutation((input: ModifyInput) =>
    api.post<QuotationDetail>(`/quotations/${id}/modify/`, input),
  );

export const useApproveQuotation = (id: string) =>
  useQuotationMutation((input: ApproveInput) =>
    api.post<QuotationDetail>(`/quotations/${id}/approve/`, input),
  );

export const useRejectQuotation = (id: string) =>
  useQuotationMutation((reason: string) =>
    api.post<QuotationDetail>(`/quotations/${id}/reject/`, { reason }),
  );

export const useLinkCustomer = (id: string) =>
  useQuotationMutation((customerId: string | null) =>
    api.post<QuotationDetail>(`/quotations/${id}/customer/`, { customer_id: customerId }),
  );

export const downloadQuotationPdf = (quotation: { id: string; number: string }) =>
  downloadFile(`/quotations/${quotation.id}/pdf/`, `${quotation.number}.pdf`);
