import { useQueries, useQuery } from "@tanstack/react-query";

import type { ListAttendanceParams } from "@/api/endpoints/attendance";
import { attendanceApi } from "@/api/endpoints/attendance";
import { qk } from "@/api/queryKeys";
import type { AttendanceLogResponse, AttendancePageResponse, AttendanceSummaryResponse } from "@/api/types";

export const useAttendanceQuery = (params: ListAttendanceParams = {}) =>
  useQuery<AttendancePageResponse>({
    queryKey: qk.attendance.list(params),
    queryFn: () => attendanceApi.list(params),
  });

export const useAttendanceSummaryQuery = (
  employeeId: number | undefined,
  from: string,
  to: string,
) =>
  useQuery<AttendanceSummaryResponse>({
    queryKey:
      employeeId !== undefined
        ? qk.attendance.summary(employeeId, from, to)
        : ["attendance", "summary", "skip"],
    queryFn: () => attendanceApi.summary({ employee_id: employeeId!, from, to }),
    enabled: employeeId !== undefined,
  });

/**
 * Для каждого сотрудника параллельно: последняя сессия, начавшаяся
 * сегодня (если есть). Возвращает Map<employeeId, AttendanceLogResponse | null>.
 *
 * `refetchInterval: 30s` — для real-time дашборда «кто где сейчас».
 */
export const useCurrentZonesQuery = (
  employeeIds: number[],
  startedFrom: string,
): Map<number, AttendanceLogResponse | null> => {
  const queries = useQueries({
    queries: employeeIds.map((id) => ({
      queryKey: qk.attendance.currentZone(id),
      queryFn: () =>
        attendanceApi.list({
          employee_id: id,
          started_from: startedFrom,
          limit: 1,
          offset: 0,
        }),
      refetchInterval: 30_000,
      staleTime: 25_000,
    })),
  });

  const result = new Map<number, AttendanceLogResponse | null>();
  employeeIds.forEach((id, idx) => {
    const q = queries[idx];
    const item = q?.data?.items[0] ?? null;
    result.set(id, item);
  });
  return result;
};
