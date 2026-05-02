import { apiClient } from "../client";
import type {
  EmployeeCreateRequest,
  EmployeeResponse,
  EmployeeUpdateRequest,
  EmployeesPageResponse,
  Role,
  SetPasswordRequest,
} from "../types";

export interface ListEmployeesParams {
  limit?: number;
  offset?: number;
  search?: string;
  role?: Role;
  is_active?: boolean;
}

export const employeesApi = {
  async list(params: ListEmployeesParams = {}): Promise<EmployeesPageResponse> {
    const { data } = await apiClient.get<EmployeesPageResponse>("/v1/employees", { params });
    return data;
  },

  async get(id: number): Promise<EmployeeResponse> {
    const { data } = await apiClient.get<EmployeeResponse>(`/v1/employees/${id}`);
    return data;
  },

  async create(req: EmployeeCreateRequest): Promise<EmployeeResponse> {
    const { data } = await apiClient.post<EmployeeResponse>("/v1/employees", req);
    return data;
  },

  async update(id: number, patch: EmployeeUpdateRequest): Promise<EmployeeResponse> {
    const { data } = await apiClient.patch<EmployeeResponse>(`/v1/employees/${id}`, patch);
    return data;
  },

  async setPassword(id: number, req: SetPasswordRequest): Promise<void> {
    await apiClient.post(`/v1/employees/${id}/password`, req);
  },

  async deactivate(id: number): Promise<EmployeeResponse> {
    const { data } = await apiClient.post<EmployeeResponse>(`/v1/employees/${id}/deactivate`);
    return data;
  },

  async activate(id: number): Promise<EmployeeResponse> {
    const { data } = await apiClient.post<EmployeeResponse>(`/v1/employees/${id}/activate`);
    return data;
  },
};
