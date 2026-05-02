/**
 * Ручные типы DTO под контракт FastAPI-бэкенда (как в `backend/README.md`).
 *
 * **TODO:** заменить на сгенерированные через `npm run gen:api`. Скрипт тянет
 * `/openapi.json` и кладёт типы в `src/api/schema.d.ts` (в `.gitignore`).
 * Этот файл — заглушка пока backend локально не запущен; контракт совпадает
 * 1-в-1, но при расхождении источник истины — `schema.d.ts`.
 *
 * Все datetime — ISO-8601 timezone-aware строки. RSSI vector: `Map<BSSID, dBm>`.
 */

// ── Auth ─────────────────────────────────────────────────────────────────────

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RefreshRequest {
  refresh_token: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface LogoutResponse {
  status: "logged_out";
}

// ── Me / User ────────────────────────────────────────────────────────────────

export type Role = "admin" | "employee";

export interface CurrentUserResponse {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  schedule_start?: string | null;
  schedule_end?: string | null;
}

// ── Employees ────────────────────────────────────────────────────────────────

export interface EmployeeResponse {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  schedule_start: string | null;
  schedule_end: string | null;
  created_at: string;
  updated_at: string;
}

export interface EmployeesPageResponse {
  items: EmployeeResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface EmployeeCreateRequest {
  email: string;
  full_name: string;
  role: Role;
  initial_password: string;
  schedule_start?: string;
  schedule_end?: string;
}

export interface EmployeeUpdateRequest {
  full_name?: string;
  role?: Role;
  schedule_start?: string;
  schedule_end?: string;
  clear_schedule_start?: boolean;
  clear_schedule_end?: boolean;
}

export interface SetPasswordRequest {
  new_password: string;
  old_password?: string;
}

// ── Zones ────────────────────────────────────────────────────────────────────

export type ZoneType = "workplace" | "corridor" | "meeting_room" | "outside_office";

export interface ZoneResponse {
  id: number;
  name: string;
  type: ZoneType;
  description: string | null;
  display_color: string | null;
}

export interface ZonesPageResponse {
  items: ZoneResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface ZoneCreateRequest {
  name: string;
  type: ZoneType;
  description?: string | null;
  display_color?: string | null;
}

export interface ZoneUpdateRequest {
  name?: string;
  type?: ZoneType;
  description?: string | null;
  display_color?: string | null;
  clear_description?: boolean;
  clear_display_color?: boolean;
}

// ── Fingerprints / Calibration ───────────────────────────────────────────────

export interface FingerprintResponse {
  id: number;
  employee_id: number | null;
  zone_id: number | null;
  is_calibration: boolean;
  captured_at: string;
  device_id: string | null;
  rssi_vector: Record<string, number>;
  sample_count: number;
}

export interface CalibrationPointCreateRequest {
  zone_id: number;
  captured_at: string;
  rssi_vector: Record<string, number>;
  sample_count?: number;
  device_id?: string;
}

// ── Attendance ───────────────────────────────────────────────────────────────

export type AttendanceStatus = "present" | "late" | "overtime" | "absent";

export interface AttendanceLogResponse {
  id: number;
  employee_id: number;
  zone_id: number;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number | null;
  status: AttendanceStatus;
  is_late: boolean;
  is_overtime: boolean;
}

export interface AttendancePageResponse {
  items: AttendanceLogResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface AttendanceSummaryResponse {
  employee_id: number;
  from: string;
  to: string;
  work_seconds_total: number;
  lateness_count: number;
  overtime_seconds_total: number;
  sessions_count: number;
}

// ── RFC 7807 Problem Details ─────────────────────────────────────────────────

export interface ProblemDetail {
  type: string;
  title: string;
  status: number;
  detail?: string;
  code?: string;
  correlation_id?: string;
  errors?: Array<{ field: string; message: string }>;
}
