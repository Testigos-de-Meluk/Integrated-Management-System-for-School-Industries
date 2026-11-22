/** Public virtual assistant API (/api/chatbot/): no account needed. */
import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api, type Paginated } from "@/shared/api/http";

export type CatalogItem = { id: string; code: string; name: string; unit_of_measure: string };

export type RequestedItem = { product_id: string; quantity: number };

export type EstimatedItem = {
  product_id: string;
  product_code: string;
  description: string;
  unit_of_measure: string;
  quantity: number;
  unit_price_min: string | null; // null = "Precio por confirmar"
  unit_price_max: string | null;
  subtotal_min: string | null;
  subtotal_max: string | null;
};

export type Estimate = {
  items: EstimatedItem[];
  total_min: string | null;
  total_max: string | null;
  unpriced_items: number;
};

export type ContactData = {
  full_name: string;
  email: string;
  phone: string;
  institution: string;
  tax_id: string;
  data_consent: boolean;
};

export type PreliminaryQuotation = Estimate & {
  id: string;
  number: string;
  issued_at: string;
  valid_until: string;
  requester_name: string;
  requester_email: string;
  estimated_dispatch_date: string | null;
  access_key: string;
};

export function usePublicCatalog(search: string, page: number) {
  return useQuery({
    queryKey: ["public-catalog", search, page],
    queryFn: () =>
      api.get<Paginated<CatalogItem>>("/chatbot/catalog/", { search, page, page_size: 12 }),
    placeholderData: keepPreviousData,
  });
}

/** Live estimate of the current selection (recomputed when it changes). */
export function useEstimate(items: RequestedItem[]) {
  return useQuery({
    queryKey: ["public-estimate", items],
    queryFn: () => api.postAnonymous<Estimate>("/chatbot/estimate/", { items }),
    enabled: items.length > 0,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });
}

export const quoteApi = {
  request: (contact: ContactData, items: RequestedItem[]) =>
    api.postAnonymous<PreliminaryQuotation>("/chatbot/quotations/", { ...contact, items }),
  email: (quotation: PreliminaryQuotation) =>
    api.postAnonymous<{ sent_to: string }>(`/chatbot/quotations/${quotation.id}/email/`, {
      key: quotation.access_key,
    }),
  pdfUrl: (quotation: PreliminaryQuotation) =>
    `/api/chatbot/quotations/${quotation.id}/pdf/?key=${encodeURIComponent(quotation.access_key)}`,
};
