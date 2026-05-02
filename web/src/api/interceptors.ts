/**
 * Axios-interceptor'ы для apiClient.
 *
 * Должен быть установлен ОДИН РАЗ на старте приложения (`installInterceptors()`
 * вызывается из `main.tsx` после ProviderScope-инициализации). Зависит от
 * `useAuthStore`, поэтому импортируется отдельным модулем — иначе client.ts
 * импортировал бы authStore, а authStore импортирует endpoints, которые
 * импортируют client.ts → циклическая зависимость.
 *
 * **Поведение:**
 * - Request: добавляет `Authorization: Bearer <access>` если access есть.
 *   Эндпоинты `/auth/login`, `/auth/refresh`, `/auth/logout` НЕ получают
 *   токен (для login и refresh — авторизация не нужна; для logout —
 *   отправляем «как есть»).
 * - Response 401 + retry-flag отсутствует:
 *   1. Через `singleflight` параллельные 401 ждут один shared refresh.
 *   2. На успех — обновляем access в store, повторяем оригинальный запрос.
 *   3. На неудачу — emit `AuthExpiredError`, store.logout(), redirect
 *      решает корневой listener (см. App.tsx).
 */
import type { AxiosError, AxiosRequestConfig, InternalAxiosRequestConfig } from "axios";
import axios from "axios";

import { useAuthStore } from "@/features/auth/authStore";

import { log } from "../lib/log";

import { apiClient } from "./client";
import { authApi } from "./endpoints/auth";
import { AuthExpiredError, parseProblemDetail } from "./errors";
import type { TokenPair } from "./types";


const AUTH_ENDPOINTS = ["/v1/auth/login", "/v1/auth/refresh", "/v1/auth/logout"];

const isAuthEndpoint = (url: string | undefined): boolean =>
  url !== undefined && AUTH_ENDPOINTS.some((p) => url.endsWith(p));

interface RetryConfig extends AxiosRequestConfig {
  _authRetried?: boolean;
}

let refreshPromise: Promise<TokenPair> | null = null;

const performRefresh = async (refreshToken: string): Promise<TokenPair> => {
  if (refreshPromise === null) {
    log.warn("[api.refresh] triggered");
    refreshPromise = authApi.refresh({ refresh_token: refreshToken }).finally(() => {
      // Освобождаем lock после ОДНОГО запроса — все ждавшие получили
      // тот же promise через ссылку выше.
      setTimeout(() => {
        refreshPromise = null;
      }, 0);
    });
  }
  return refreshPromise;
};

export const installInterceptors = (): void => {
  apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    if (isAuthEndpoint(config.url)) return config;
    const token = useAuthStore.getState().accessToken;
    if (token !== null && token.length > 0) {
      config.headers.set("Authorization", `Bearer ${token}`);
    }
    return config;
  });

  apiClient.interceptors.response.use(
    (response) => response,
    async (error: AxiosError): Promise<unknown> => {
      const status = error.response?.status;
      const config = error.config as RetryConfig | undefined;
      if (config === undefined || status !== 401 || config._authRetried === true) {
        return Promise.reject(error);
      }
      if (isAuthEndpoint(config.url)) {
        return Promise.reject(error);
      }

      const store = useAuthStore.getState();
      const refresh = store.refreshToken;
      if (refresh === null || refresh.length === 0) {
        store.logout().catch(() => {});
        return Promise.reject(new AuthExpiredError(error));
      }

      try {
        const tokens = await performRefresh(refresh);
        store.setAccessToken(tokens.access_token);
        store.setRefreshToken(tokens.refresh_token);
        config._authRetried = true;
        if (config.headers !== undefined) {
          (config.headers as Record<string, string>)["Authorization"] =
            `Bearer ${tokens.access_token}`;
        }
        log.info("[api.refresh] success");
        return apiClient.request(config);
      } catch (refreshError) {
        const parsed = parseProblemDetail(refreshError);
        log.error("[api.refresh] failed", { message: parsed.message });
        await store.logout().catch(() => {});
        return Promise.reject(new AuthExpiredError(refreshError));
      }
    },
  );
};

// Re-export для удобства. Не вызывает install сам — это делает main.tsx,
// чтобы порядок боков был детерминирован.
export { axios };
