/** Data layer of the Odoo export queue and batches (/api/accounting-export/): EXPORT_QUEUE_MANAGE. */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { WorkOrderStatus } from "@/features/work-orders/api";
import { api, downloadFile, type Paginated } from "@/shared/api/http";

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

export type BatchWorkOrder = {
  work_order_id: string;
  number: string;
  customer_name: string;
  status: WorkOrderStatus;
  cancelled_after_export: boolean;
};

export type ExportBatch = {
  id: string;
  file_name: string;
  created_at: string;
  created_by_name: string;
  work_orders: BatchWorkOrder[];
};

export function useExportBatches(page: number, pageSize = 20) {
  return useQuery({
    queryKey: ["export-batches", { page }],
    queryFn: () =>
      api.get<Paginated<ExportBatch>>("/accounting-export/batches/", { page, page_size: pageSize }),
    placeholderData: keepPreviousData,
  });
}

export function downloadBatch(batch: Pick<ExportBatch, "id" | "file_name">): Promise<void> {
  return downloadFile(`/accounting-export/batches/${batch.id}/file/`, batch.file_name);
}

/** Generates the batch (the O.T.s become "Registrada en Odoo") and downloads its file. */
export function useExportWorkOrders() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (workOrderIds: string[]) =>
      api.post<ExportBatch>("/accounting-export/batches/", { work_order_ids: workOrderIds }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["export-queue"] });
      void queryClient.invalidateQueries({ queryKey: ["export-batches"] });
      void queryClient.invalidateQueries({ queryKey: ["work-orders"] });
      void queryClient.invalidateQueries({ queryKey: ["customers"] }); // 360 history statuses
    },
  });
}
