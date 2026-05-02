import { LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { useAuthStore } from "@/features/auth/authStore";
import { ROUTES } from "@/routes/routes";

export const Topbar = (): JSX.Element => {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.currentUser);
  const logout = useAuthStore((s) => s.logout);

  const onLogout = async (): Promise<void> => {
    await logout();
    navigate(ROUTES.login, { replace: true });
  };

  return (
    <div
      style={{
        height: "100%",
        background: "var(--color-surface)",
        borderBottom: "1px solid var(--color-border)",
        padding: "0 var(--space-5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      <strong>Светлячок · Админ-панель</strong>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
        {user !== null && (
          <span style={{ fontSize: 13, color: "var(--color-fg-muted)" }}>
            {user.full_name} ({user.role})
          </span>
        )}
        <button
          type="button"
          onClick={onLogout}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-2)",
            background: "transparent",
            border: "1px solid var(--color-border)",
            padding: "var(--space-2) var(--space-3)",
            borderRadius: "var(--radius-md)",
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          <LogOut size={14} />
          Выйти
        </button>
      </div>
    </div>
  );
};
