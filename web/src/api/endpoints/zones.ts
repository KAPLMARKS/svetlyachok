import { apiClient } from "../client";
import type {
  ZoneCreateRequest,
  ZoneResponse,
  ZoneUpdateRequest,
  ZonesPageResponse,
} from "../types";

export const zonesApi = {
  async list(): Promise<ZoneResponse[]> {
    const { data } = await apiClient.get<ZonesPageResponse>("/v1/zones");
    return data.items;
  },

  async get(id: number): Promise<ZoneResponse> {
    const { data } = await apiClient.get<ZoneResponse>(`/v1/zones/${id}`);
    return data;
  },

  async create(req: ZoneCreateRequest): Promise<ZoneResponse> {
    const { data } = await apiClient.post<ZoneResponse>("/v1/zones", req);
    return data;
  },

  async update(id: number, patch: ZoneUpdateRequest): Promise<ZoneResponse> {
    const { data } = await apiClient.patch<ZoneResponse>(`/v1/zones/${id}`, patch);
    return data;
  },

  async delete(id: number): Promise<void> {
    await apiClient.delete(`/v1/zones/${id}`);
  },
};
