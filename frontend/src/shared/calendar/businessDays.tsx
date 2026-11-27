/**
 * Business days (Monday to Friday, minus Colombian public holidays). The holidays come from the
 * backend (/api/calendar/holidays/), the single source of truth; the screens only WARN when a date
 * is not a business day (step 5b decision), they never block.
 */
import { useQuery } from "@tanstack/react-query";

import { api } from "@/shared/api/http";

type HolidaysResponse = { year: number; holidays: string[] };

function useHolidays(year: number | null) {
  return useQuery({
    queryKey: ["calendar", "holidays", year],
    queryFn: () => api.get<HolidaysResponse>("/calendar/holidays/", { year: year ?? undefined }),
    enabled: year !== null,
    staleTime: Infinity, // a year's holidays never change
  });
}

/** "2026-12-25" → why it is not a business day, or null if it is (or while loading). */
export function useNonBusinessDayReason(isoDate: string | null | undefined): string | null {
  const year = isoDate ? Number(isoDate.slice(0, 4)) : null;
  const { data } = useHolidays(year && year >= 2000 && year <= 2100 ? year : null);
  if (!isoDate || !data) return null;
  const [y, m, d] = isoDate.split("-").map(Number);
  const weekday = new Date(y, m - 1, d).getDay();
  if (weekday === 0) return "domingo";
  if (weekday === 6) return "sábado";
  return data.holidays.includes(isoDate) ? "festivo" : null;
}

/** Amber warning under a date field when the chosen date is not a business day. */
export function NonBusinessDayWarning({ date }: { date: string | null | undefined }) {
  const reason = useNonBusinessDayReason(date);
  if (!reason) return null;
  return (
    <p role="status" className="mt-1 rounded-md bg-amber-50 px-2 py-1 text-xs text-amber-900">
      La fecha elegida es {reason}: no es un día hábil. Revísela antes de guardar.
    </p>
  );
}
