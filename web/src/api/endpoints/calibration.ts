import { apiClient } from "../client";
import type {
  CalibrationPointCreateRequest,
  FingerprintResponse,
} from "../types";

export const calibrationApi = {
  async list(zoneId?: number): Promise<FingerprintResponse[]> {
    const params = zoneId !== undefined ? { zone_id: zoneId } : undefined;
    const { data } = await apiClient.get<FingerprintResponse[]>(
      "/v1/calibration/points",
      { params },
    );
    return data;
  },

  async create(req: CalibrationPointCreateRequest): Promise<FingerprintResponse> {
    const { data } = await apiClient.post<FingerprintResponse>(
      "/v1/calibration/points",
      req,
    );
    return data;
  },

  async delete(id: number): Promise<void> {
    await apiClient.delete(`/v1/calibration/points/${id}`);
  },
};
