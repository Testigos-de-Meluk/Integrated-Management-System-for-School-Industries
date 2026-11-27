/** Data layer of customers and their commercial notes (/api/customers/). */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Paginated } from "@/shared/api/http";

export type CustomerType = "NATURAL_PERSON" | "LEGAL_ENTITY";
export type CustomerStatus = "ACTIVE" | "INACTIVE";

export const TYPE_LABELS: Record<CustomerType, string> = {
  NATURAL_PERSON: "Persona natural",
  LEGAL_ENTITY: "Persona jurídica",
};
export const STATUS_LABELS: Record<CustomerStatus, string> = { ACTIVE: "Activo", INACTIVE: "Inactivo" };

/** Labels that depend on the customer type (full name vs. business name, document vs. NIT). */
export const FIELD_LABELS: Record<CustomerType, { name: string; taxId: string; taxIdHint: string }> = {
  NATURAL_PERSON: {
    name: "Nombre completo",
    taxId: "Número de documento",
    taxIdHint: "De 5 a 15 dígitos, sin puntos.",
  },
  LEGAL_ENTITY: {
    name: "Razón social",
    taxId: "NIT",
    taxIdHint: "Con dígito de verificación, por ejemplo 900456789-1.",
  },
};

export type Customer = {
  id: string;
  customer_type: CustomerType;
  tax_id: string;
  name: string;
  address: string;
  primary_phone: string;
  email: string;
  commercial_contact: string;
  status: CustomerStatus;
  is_active: boolean;
};

export type CustomerFilters = {
  tax_id?: string;
  name?: string;
  commercial_contact?: string;
  status?: CustomerStatus | "";
};

export type CustomerFields = {
  name: string;
  address: string;
  primary_phone: string;
  email: string;
  commercial_contact: string;
};
export type NewCustomer = CustomerFields & { customer_type: CustomerType; tax_id: string };

export type HistoryType = "QUOTATION" | "WORK_ORDER";

export type HistoryEntry = {
  id: string;
  document_type: HistoryType;
  reference: string;
  date: string;
  status: string;
};

export type Note = {
  id: string;
  content: string;
  author_name: string;
  created_at: string;
  is_edited: boolean;
  updated_at: string | null;
  updated_by_name: string;
  can_edit: boolean;
};

const keys = {
  all: ["customers"] as const,
  list: (filters: CustomerFilters, page: number) => [...keys.all, "list", { ...filters, page }] as const,
  byTaxId: (taxId: string) => [...keys.all, "by-tax-id", taxId] as const,
  history: (id: string, type: HistoryType, page: number) => [...keys.all, id, "history", type, page] as const,
  notes: (id: string, page: number) => [...keys.all, id, "notes", page] as const,
};

export function useCustomers(filters: CustomerFilters, page: number, pageSize = 20) {
  return useQuery({
    queryKey: keys.list(filters, page),
    queryFn: () => api.get<Paginated<Customer>>("/customers/", { ...filters, page, page_size: pageSize }),
    placeholderData: keepPreviousData,
  });
}

export function useCustomerByTaxId(taxId: string) {
  return useQuery({
    queryKey: keys.byTaxId(taxId),
    queryFn: () => api.get<Customer>(`/customers/by-tax-id/${encodeURIComponent(taxId)}/`),
    retry: false,
  });
}

export function useCustomerHistory(customerId: string | undefined, type: HistoryType, page: number) {
  return useQuery({
    queryKey: keys.history(customerId ?? "", type, page),
    queryFn: () =>
      api.get<Paginated<HistoryEntry>>(`/customers/${customerId}/history/`, {
        type,
        page,
        page_size: 20,
      }),
    enabled: Boolean(customerId),
  });
}

export function useNotes(customerId: string | undefined, page: number) {
  return useQuery({
    queryKey: keys.notes(customerId ?? "", page),
    queryFn: () => api.get<Paginated<Note>>(`/customers/${customerId}/notes/`, { page, page_size: 10 }),
    enabled: Boolean(customerId),
    placeholderData: keepPreviousData,
  });
}

function useCustomerMutation<TInput, TResult>(request: (input: TInput) => Promise<TResult>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: request,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

export const useCreateCustomer = () =>
  useCustomerMutation((input: NewCustomer) => api.post<Customer>("/customers/", input));

export const useUpdateCustomer = () =>
  useCustomerMutation(({ id, ...input }: CustomerFields & { id: string }) =>
    api.patch<Customer>(`/customers/${id}/`, input),
  );

export const useCustomerStatus = () =>
  useCustomerMutation(({ id, activate }: { id: string; activate: boolean }) =>
    api.post<Customer>(`/customers/${id}/${activate ? "activate" : "deactivate"}/`),
  );

export const useAddNote = () =>
  useCustomerMutation(({ customerId, content }: { customerId: string; content: string }) =>
    api.post<Note>(`/customers/${customerId}/notes/`, { content }),
  );

export const useEditNote = () =>
  useCustomerMutation(
    ({ customerId, noteId, content }: { customerId: string; noteId: string; content: string }) =>
      api.patch<Note>(`/customers/${customerId}/notes/${noteId}/`, { content }),
  );

export const useDeleteNote = () =>
  useCustomerMutation(({ customerId, noteId }: { customerId: string; noteId: string }) =>
    api.delete<void>(`/customers/${customerId}/notes/${noteId}/`),
  );
