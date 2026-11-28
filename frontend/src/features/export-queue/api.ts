/** Data layer of the Siigo export queue (/api/accounting-export/): EXPORT_QUEUE_MANAGE. */
import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api, type Paginated } from "@/shared/api/http";

export type QueueItem = {
  product_code: string;
  description: string;
  unit_of_measure: string;
  quantity: number;
};

export type QueueEntry = {
  work_order_id: string;
  number: string;
  quotation_number: string;
  created_at: string;
  enqueued_at: string;
  customer_tax_id: string;
  customer_name: string;
  items: QueueItem[];
  agreed_delivery_date: string;
};

export type QueueFilters = {
  created_from?: string;
  created_to?: string;
  customer?: string;
  number?: string;
};

export function useExportQueue(filters: QueueFilters, page: number, pageSize = 20) {
  return useQuery({
    queryKey: ["export-queue", { ...filters, page }],
    queryFn: () =>
      api.get<Paginated<QueueEntry>>("/accounting-export/queue/", {
        ...filters,
        page,
        page_size: pageSize,
      }),
    placeholderData: keepPreviousData,
  });
}
