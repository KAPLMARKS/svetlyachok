import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useNavigate } from "react-router-dom";

import { getErrorMessage } from "@/lib/errorMessages";
import { ROUTES } from "@/routes/routes";

import { useAuthStore } from "./authStore";
import type { LoginInput } from "./schema";
import { loginSchema } from "./schema";


export const LoginPage = (): JSX.Element => {
  const navigate = useNavigate();
  const login = useAuthStore((s) => s.login);
  const status = useAuthStore((s) => s.status);
  const currentUser = useAuthStore((s) => s.currentUser);

  const [submitError, setSubmitError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginInput>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  if (currentUser !== null) {
    return <Navigate to={ROUTES.dashboard} replace />;
  }

  const onSubmit = async (input: LoginInput): Promise<void> => {
    setSubmitError(null);
    try {
      await login(input.email, input.password);
      navigate(ROUTES.dashboard, { replace: true });
    } catch (error) {
      setSubmitError(getErrorMessage(error));
    }
  };

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--color-bg)",
      }}
    >
      <form
        onSubmit={handleSubmit(onSubmit)}
        style={{
          background: "var(--color-surface)",
          padding: "var(--space-6)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-md)",
          width: "100%",
          maxWidth: 400,
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-4)",
        }}
      >
        <h1 style={{ margin: 0, textAlign: "center" }}>Светлячок</h1>
        <p style={{ margin: 0, textAlign: "center", color: "var(--color-fg-muted)" }}>
          Админ-панель
        </p>

        {submitError !== null && (
          <div
            role="alert"
            style={{
              padding: "var(--space-3)",
              background: "#fed7d7",
              color: "var(--color-danger-hover)",
              borderRadius: "var(--radius-md)",
              fontSize: 13,
            }}
          >
            {submitError}
          </div>
        )}

        <label style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
          <span style={{ fontSize: 13, fontWeight: 500 }}>Email</span>
          <input
            type="email"
            autoComplete="username"
            disabled={isSubmitting || status === "loading"}
            {...register("email")}
            style={{
              padding: "var(--space-3)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-md)",
              fontSize: 14,
            }}
          />
          {errors.email && (
            <span style={{ color: "var(--color-danger)", fontSize: 12 }}>
              {errors.email.message}
            </span>
          )}
        </label>

        <label style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
          <span style={{ fontSize: 13, fontWeight: 500 }}>Пароль</span>
          <input
            type="password"
            autoComplete="current-password"
            disabled={isSubmitting || status === "loading"}
            {...register("password")}
            style={{
              padding: "var(--space-3)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-md)",
              fontSize: 14,
            }}
          />
          {errors.password && (
            <span style={{ color: "var(--color-danger)", fontSize: 12 }}>
              {errors.password.message}
            </span>
          )}
        </label>

        <button
          type="submit"
          disabled={isSubmitting || status === "loading"}
          style={{
            padding: "var(--space-3)",
            background: "var(--color-primary)",
            color: "var(--color-primary-fg)",
            border: "none",
            borderRadius: "var(--radius-md)",
            fontSize: 14,
            fontWeight: 600,
          }}
        >
          {isSubmitting || status === "loading" ? "Входим…" : "Войти"}
        </button>
      </form>
    </main>
  );
};
