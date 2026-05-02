/**
 * Zustand-store для auth-состояния.
 *
 * **Стратегия хранения токенов:**
 * - `accessToken` — в памяти (Zustand state). На F5 теряется и
 *   восстанавливается через `bootstrapFromRefresh()`.
 * - `refreshToken` — в `localStorage` (`svetlyachok.refresh`). На F5
 *   читаем оттуда и обмениваем через `POST /auth/refresh`. XSS может
 *   стянуть, но backend не даёт httpOnly cookie на пилоте, и переход
 *   на cookie-based auth — backend-задача за рамками вехи.
 * - `currentUser` — в памяти. Подтягивается через `GET /me` после login
 *   или после успешного refresh.
 */
import { create } from "zustand";

import { authApi } from "../../api/endpoints/auth";
import { parseProblemDetail } from "../../api/errors";
import type { CurrentUserResponse } from "../../api/types";
import { log } from "../../lib/log";

const REFRESH_STORAGE_KEY = "svetlyachok.refresh";

const readRefreshFromStorage = (): string | null => {
  try {
    return window.localStorage.getItem(REFRESH_STORAGE_KEY);
  } catch {
    return null;
  }
};

const writeRefreshToStorage = (token: string | null): void => {
  try {
    if (token === null) {
      window.localStorage.removeItem(REFRESH_STORAGE_KEY);
    } else {
      window.localStorage.setItem(REFRESH_STORAGE_KEY, token);
    }
  } catch {
    // localStorage недоступен (в SSR, в private mode); игнорируем.
  }
};

type AuthStatus = "idle" | "loading" | "authenticated" | "anonymous";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  currentUser: CurrentUserResponse | null;
  status: AuthStatus;

  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  bootstrapFromRefresh: () => Promise<void>;
  setAccessToken: (token: string) => void;
  setRefreshToken: (token: string) => void;
  setCurrentUser: (user: CurrentUserResponse | null) => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: null,
  refreshToken: readRefreshFromStorage(),
  currentUser: null,
  status: "idle",

  setAccessToken: (token: string) => {
    log.debug("[auth.setAccessToken] updated");
    set({ accessToken: token });
  },

  setRefreshToken: (token: string) => {
    writeRefreshToStorage(token);
    set({ refreshToken: token });
  },

  setCurrentUser: (user) => {
    set({ currentUser: user, status: user !== null ? "authenticated" : "anonymous" });
  },

  async login(email: string, password: string) {
    set({ status: "loading" });
    try {
      const tokens = await authApi.login({ email, password });
      writeRefreshToStorage(tokens.refresh_token);
      set({
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
      });
      const user = await authApi.getMe();
      set({ currentUser: user, status: "authenticated" });
      log.info("[auth.login] success", { userId: user.id, role: user.role });
    } catch (error) {
      log.warn("[auth.login] failed", { error: parseProblemDetail(error).message });
      set({
        accessToken: null,
        refreshToken: null,
        currentUser: null,
        status: "anonymous",
      });
      writeRefreshToStorage(null);
      throw error;
    }
  },

  async logout() {
    log.info("[auth.logout] start");
    try {
      await authApi.logout();
    } catch {
      // best-effort: серверный logout может упасть; локально всё равно чистим.
    }
    writeRefreshToStorage(null);
    set({
      accessToken: null,
      refreshToken: null,
      currentUser: null,
      status: "anonymous",
    });
    log.info("[auth.logout] cleared");
  },

  async bootstrapFromRefresh() {
    const refresh = get().refreshToken;
    if (refresh === null || refresh.length === 0) {
      set({ status: "anonymous" });
      return;
    }
    set({ status: "loading" });
    try {
      const tokens = await authApi.refresh({ refresh_token: refresh });
      writeRefreshToStorage(tokens.refresh_token);
      set({
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
      });
      const user = await authApi.getMe();
      set({ currentUser: user, status: "authenticated" });
      log.info("[auth.bootstrap] restored", { userId: user.id });
    } catch (error) {
      log.warn("[auth.bootstrap] refresh_failed", {
        error: parseProblemDetail(error).message,
      });
      writeRefreshToStorage(null);
      set({
        accessToken: null,
        refreshToken: null,
        currentUser: null,
        status: "anonymous",
      });
    }
  },
}));
