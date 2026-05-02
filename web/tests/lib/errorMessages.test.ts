import { describe, expect, it } from "vitest";

import { ApiError, NetworkError } from "../../src/api/errors";
import { getErrorMessage } from "../../src/lib/errorMessages";

describe("getErrorMessage", () => {
  it("network error → русское сообщение про подключение", () => {
    expect(getErrorMessage(new NetworkError())).toMatch(/Не удалось связаться/);
  });

  it("известный code → текст из словаря", () => {
    const err = new ApiError(
      "...",
      401,
      "invalid_credentials",
      undefined,
      undefined,
      undefined,
      undefined,
    );
    expect(getErrorMessage(err)).toBe("Неверный email или пароль");
  });

  it("неизвестный code, есть detail → fallback на detail", () => {
    const err = new ApiError("...", 500, "unknown_code", "что-то сломалось", undefined, undefined, undefined);
    expect(getErrorMessage(err)).toBe("что-то сломалось");
  });

  it("совсем нечего показать → общий fallback", () => {
    expect(getErrorMessage(undefined)).toMatch(/Ошибка сервера/);
  });
});
