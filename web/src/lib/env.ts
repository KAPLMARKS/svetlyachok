/**
 * Доступ к Vite env-переменным с явной типизацией и default-значениями.
 *
 * Все `VITE_*` переменные читаются один раз на старте приложения; здесь же
 * валидируем, что обязательные не пустые. На пилоте обязательных нет —
 * `VITE_API_BASE_URL` имеет default `/api`, который попадает в dev-proxy.
 */
import { log } from "./log";

const readBaseUrl = (): string => {
  const raw = import.meta.env.VITE_API_BASE_URL;
  if (typeof raw === "string" && raw.length > 0) return raw;
  return "/api";
};

export const env = {
  apiBaseUrl: readBaseUrl(),
  isDev: import.meta.env.DEV,
  isProd: import.meta.env.PROD,
} as const;

log.debug("[env] loaded", { apiBaseUrl: env.apiBaseUrl, dev: env.isDev });
