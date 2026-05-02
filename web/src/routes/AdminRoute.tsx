import { toast } from "react-hot-toast";
import { Navigate, Outlet } from "react-router-dom";

import { useAuthStore } from "@/features/auth/authStore";
import { log } from "@/lib/log";
import { ROUTES } from "@/routes/routes";

export const AdminRoute = (): JSX.Element => {
  const user = useAuthStore((s) => s.currentUser);

  if (user !== null && user.role !== "admin") {
    log.debug("[routes] guard.deny", { route: "admin", reason: "not_admin" });
    toast.error("Доступ только для администратора");
    return <Navigate to={ROUTES.dashboard} replace />;
  }
  return <Outlet />;
};
