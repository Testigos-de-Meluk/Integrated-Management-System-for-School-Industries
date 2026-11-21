import { useQuery } from "@tanstack/react-query";

import { ApiError, apiGet } from "@/shared/api/http";

export type HealthStatus = {
  status: "ok" | "degraded";
  checks: Record<string, "ok" | "unavailable">;
};

export function useHealth() {
  return useQuery({
    queryKey: ["system", "health"],
    queryFn: async () => {
      try {
        return await apiGet<HealthStatus>("/health/");
      } catch (error) {
        // A 503 response still carries the detailed checks.
        if (error instanceof ApiError && error.status === 503) {
          return error.body as HealthStatus;
        }
        throw error;
      }
    },
  });
}
