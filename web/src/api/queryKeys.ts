/**
 * Типизированный builder query-ключей для TanStack Query.
 *
 * Иерархия ключей даёт нам два важных свойства:
 * - `qk.employees._all` — invalidate все queries по employees (после CRUD)
 * - `qk.employees.list({...})` — конкретный список с фильтрами для cache hit
 */
import type { ListAttendanceParams } from "./endpoints/attendance";
import type { ListEmployeesParams } from "./endpoints/employees";

export const qk = {
  me: () => ["me"] as const,

  employees: {
    _all: ["employees"] as const,
    list: (params: ListEmployeesParams = {}) => ["employees", "list", params] as const,
    detail: (id: number) => ["employees", "detail", id] as const,
  },

  zones: {
    _all: ["zones"] as const,
    list: () => ["zones", "list"] as const,
    detail: (id: number) => ["zones", "detail", id] as const,
  },

  calibration: {
    _all: ["calibration"] as const,
    list: (zoneId?: number) => ["calibration", "list", { zoneId }] as const,
  },

  attendance: {
    _all: ["attendance"] as const,
    list: (params: ListAttendanceParams = {}) => ["attendance", "list", params] as const,
    summary: (employeeId: number, from: string, to: string) =>
      ["attendance", "summary", employeeId, from, to] as const,
    currentZone: (employeeId: number) =>
      ["attendance", "currentZone", employeeId] as const,
  },
} as const;
