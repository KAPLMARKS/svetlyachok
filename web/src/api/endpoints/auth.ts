import { log } from "../../lib/log";
import { apiClient } from "../client";
import type {
  CurrentUserResponse,
  LoginRequest,
  LogoutResponse,
  RefreshRequest,
  TokenPair,
} from "../types";

export const authApi = {
  async login(req: LoginRequest): Promise<TokenPair> {
    log.debug("[api.auth.login] start", { email: req.email });
    const { data } = await apiClient.post<TokenPair>("/v1/auth/login", req);
    return data;
  },

  async refresh(req: RefreshRequest): Promise<TokenPair> {
    log.debug("[api.auth.refresh] start");
    const { data } = await apiClient.post<TokenPair>("/v1/auth/refresh", req);
    return data;
  },

  async logout(): Promise<LogoutResponse> {
    log.debug("[api.auth.logout] start");
    const { data } = await apiClient.post<LogoutResponse>("/v1/auth/logout");
    return data;
  },

  async getMe(): Promise<CurrentUserResponse> {
    const { data } = await apiClient.get<CurrentUserResponse>("/v1/me");
    return data;
  },
};
