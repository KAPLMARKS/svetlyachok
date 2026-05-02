import "@testing-library/jest-dom";
import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "./msw/server";

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

afterEach(() => {
  server.resetHandlers();
  // Сбрасываем localStorage между тестами, чтобы Zustand-store auth
  // и сохранённые refresh-токены не утекали из теста в тест.
  try {
    window.localStorage.clear();
  } catch {
    // jsdom иногда не предоставляет clear (Node 25 + experimental localstorage).
  }
});

afterAll(() => {
  server.close();
});
