/**
 * Shared axios-клиент. Interceptor'ы (auth-bearer / auth-refresh) добавляются
 * в `client.installInterceptors()` после инициализации Zustand auth store —
 * это решает ситуацию с круговой зависимостью (api/client → authStore →
 * api/endpoints → api/client).
 */
import axios from "axios";

import { env } from "../lib/env";

export const apiClient = axios.create({
  baseURL: env.apiBaseUrl,
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
});
