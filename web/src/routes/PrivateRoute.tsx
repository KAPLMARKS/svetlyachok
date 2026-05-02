import { Navigate, Outlet } from "react-router-dom";

import { useAuthStore } from "@/features/auth/authStore";
import { log } from "@/lib/log";
import { ROUTES } from "@/routes/routes";

export const PrivateRoute = (): JSX.Element => {
  const status = useAuthStore((s) => s.status);
  const user = useAuthStore((s) => s.currentUser);

  if (status === "loading" || status === "idle") {
    return (
      <div style={{ padding: "var(--space-6)", textAlign: "center" }}>Загрузка…</div>
    );
  }
  if (user === null) {
    log.debug("[routes] guard.deny", { route: "private", reason: "no_user" });
    return <Navigate to={ROUTES.login} replace />;
  }
  return <Outlet />;
};
