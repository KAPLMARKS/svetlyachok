/**
 * RFC 7807 Problem Details → структурированные классы ошибок.
 *
 * Backend всегда возвращает ошибки в формате
 * `{ type, title, status, detail, code, correlation_id, errors? }`.
 * Этот модуль превращает любой `unknown` от axios в типизированный объект,
 * пригодный для UI (toast/inline) и логирования (correlation_id).
 */
import axios, { type AxiosError } from "axios";

import type { ProblemDetail } from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string | undefined,
    public readonly detail: string | undefined,
    public readonly correlationId: string | undefined,
    public readonly fieldErrors: Array<{ field: string; message: string }> | undefined,
    public readonly raw: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Refresh не удался / refresh-токен невалиден / истёк. Catch'ится в
 * глобальном listener'е, чтобы редиректнуть на /login и почистить store.
 */
export class AuthExpiredError extends ApiError {
  constructor(raw: unknown) {
    super("Сессия истекла, войдите снова", 401, "auth_expired", undefined, undefined, undefined, raw);
    this.name = "AuthExpiredError";
  }
}

/**
 * Сеть/таймаут — не дошли до backend. Отдельный класс, чтобы UI мог
 * предложить «проверьте подключение» вместо «сервер вернул ошибку».
 */
export class NetworkError extends Error {
  constructor(
    message = "Не удалось связаться с сервером",
    public readonly raw?: unknown,
  ) {
    super(message);
    this.name = "NetworkError";
  }
}

const isProblemDetail = (data: unknown): data is ProblemDetail => {
  if (typeof data !== "object" || data === null) return false;
  const candidate = data as Partial<ProblemDetail>;
  return typeof candidate.status === "number";
};

export const parseProblemDetail = (error: unknown): ApiError | NetworkError => {
  if (axios.isAxiosError(error)) {
    return parseAxiosError(error);
  }
  if (error instanceof Error) {
    return new NetworkError(error.message, error);
  }
  return new NetworkError(undefined, error);
};

const parseAxiosError = (error: AxiosError): ApiError | NetworkError => {
  if (!error.response) {
    return new NetworkError(error.message || undefined, error);
  }
  const status = error.response.status;
  const data = error.response.data;

  if (isProblemDetail(data)) {
    return new ApiError(
      data.title ?? "Ошибка сервера",
      data.status,
      data.code,
      data.detail,
      data.correlation_id,
      data.errors,
      data,
    );
  }
  // Backend в forge-режиме (proxy / nginx) может вернуть не-RFC7807 ошибку.
  return new ApiError(
    error.message || `HTTP ${status}`,
    status,
    undefined,
    undefined,
    undefined,
    undefined,
    data,
  );
};
