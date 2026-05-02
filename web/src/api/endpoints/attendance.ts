import { apiClient } from "../client";
import type {
  AttendancePageResponse,
  AttendanceStatus,
  AttendanceSummaryResponse,
} from "../types";

export interface ListAttendanceParams {
  employee_id?: number;
  zone_id?: number;
  status?: AttendanceStatus;
  started_from?: string;
  started_to?: string;
  limit?: number;
  offset?: number;
}

export interface AttendanceSummaryParams {
  employee_id: number;
  from: string;
  to: string;
}

export const attendanceApi = {
  async list(params: ListAttendanceParams = {}): Promise<AttendancePageResponse> {
    const { data } = await apiClient.get<AttendancePageResponse>("/v1/attendance", { params });
    return data;
  },

  async summary(params: AttendanceSummaryParams): Promise<AttendanceSummaryResponse> {
    const { data } = await apiClient.get<AttendanceSummaryResponse>("/v1/attendance/summary", {
      params,
    });
    return data;
  },
};
