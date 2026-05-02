/**
 * Default MSW-handler'ы для всех endpoint'ов.
 *
 * Каждый возвращает «happy path» с фиксированными фикстурами. В конкретных
 * тестах через `server.use(http.method(...).respondWith(...))` можно
 * переопределить под нужный сценарий (401/409/503/...).
 */
import { http, HttpResponse } from "msw";

import type {
  AttendanceLogResponse,
  AttendancePageResponse,
  AttendanceSummaryResponse,
  CurrentUserResponse,
  EmployeeResponse,
  EmployeesPageResponse,
  FingerprintResponse,
  TokenPair,
  ZoneResponse,
  ZonesPageResponse,
} from "../../src/api/types";

const API = "/api/v1";

const sampleAdmin: CurrentUserResponse = {
  id: 1,
  email: "admin@svetlyachok.local",
  full_name: "Иванов И.И.",
  role: "admin",
  is_active: true,
  schedule_start: "09:00:00",
  schedule_end: "18:00:00",
};

const sampleTokens: TokenPair = {
  access_token: "test.access.token",
  refresh_token: "test.refresh.token",
  token_type: "bearer",
  expires_in: 1800,
};

const sampleEmployees: EmployeeResponse[] = [
  {
    id: 1,
    email: "admin@svetlyachok.local",
    full_name: "Иванов И.И.",
    role: "admin",
    is_active: true,
    schedule_start: "09:00:00",
    schedule_end: "18:00:00",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: 2,
    email: "petrov@svetlyachok.local",
    full_name: "Петров П.П.",
    role: "employee",
    is_active: true,
    schedule_start: "09:00:00",
    schedule_end: "18:00:00",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

const sampleZones: ZoneResponse[] = [
  { id: 1, name: "Рабочее место 1", type: "workplace", description: null, display_color: "#1e88e5" },
  { id: 2, name: "Коридор", type: "corridor", description: null, display_color: "#718096" },
  {
    id: 3,
    name: "Переговорная",
    type: "meeting_room",
    description: "Большая",
    display_color: "#38a169",
  },
];

const sampleFingerprint: FingerprintResponse = {
  id: 100,
  employee_id: 1,
  zone_id: 1,
  is_calibration: true,
  captured_at: "2026-05-01T10:00:00Z",
  device_id: "test-device",
  rssi_vector: { "AA:BB:CC:DD:EE:01": -55, "AA:BB:CC:DD:EE:02": -65 },
  sample_count: 1,
};

const sampleAttendance: AttendanceLogResponse = {
  id: 500,
  employee_id: 1,
  zone_id: 1,
  started_at: "2026-05-01T09:05:00Z",
  ended_at: null,
  duration_seconds: null,
  status: "present",
  is_late: false,
  is_overtime: false,
};

export const handlers = [
  http.post(`${API}/auth/login`, () => HttpResponse.json(sampleTokens)),
  http.post(`${API}/auth/refresh`, () => HttpResponse.json(sampleTokens)),
  http.post(`${API}/auth/logout`, () => HttpResponse.json({ status: "logged_out" })),
  http.get(`${API}/me`, () => HttpResponse.json(sampleAdmin)),

  http.get(`${API}/employees`, () =>
    HttpResponse.json<EmployeesPageResponse>({
      items: sampleEmployees,
      total: sampleEmployees.length,
      limit: 20,
      offset: 0,
    }),
  ),
  http.get(`${API}/employees/:id`, ({ params }) => {
    const id = Number(params["id"]);
    const found = sampleEmployees.find((e) => e.id === id);
    if (found === undefined) return new HttpResponse(null, { status: 404 });
    return HttpResponse.json<EmployeeResponse>(found);
  }),

  http.get(`${API}/zones`, () =>
    HttpResponse.json<ZonesPageResponse>({
      items: sampleZones,
      total: sampleZones.length,
      limit: 100,
      offset: 0,
    }),
  ),

  http.get(`${API}/calibration/points`, () => HttpResponse.json([sampleFingerprint])),

  http.get(`${API}/attendance`, () =>
    HttpResponse.json<AttendancePageResponse>({
      items: [sampleAttendance],
      total: 1,
      limit: 50,
      offset: 0,
    }),
  ),
  http.get(`${API}/attendance/summary`, () =>
    HttpResponse.json<AttendanceSummaryResponse>({
      employee_id: 1,
      from: "2026-05-01T00:00:00Z",
      to: "2026-05-31T23:59:59Z",
      work_seconds_total: 360000,
      lateness_count: 2,
      overtime_seconds_total: 7200,
      sessions_count: 22,
    }),
  ),
];
