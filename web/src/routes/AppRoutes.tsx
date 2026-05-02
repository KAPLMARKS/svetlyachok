import { Navigate, Route, Routes } from "react-router-dom";

import { AttendanceDashboardPage } from "@/features/attendance/AttendanceDashboardPage";
import { EmployeeAttendancePage } from "@/features/attendance/EmployeeAttendancePage";
import { LoginPage } from "@/features/auth/LoginPage";
import { EmployeesListPage } from "@/features/employees/EmployeesListPage";
import { RadiomapPage } from "@/features/radiomap/RadiomapPage";
import { ZonesListPage } from "@/features/zones/ZonesListPage";
import { AppShell } from "@/layout/AppShell";

import { AdminRoute } from "./AdminRoute";
import { PrivateRoute } from "./PrivateRoute";
import { ROUTES } from "./routes";

const NotFound = (): JSX.Element => (
  <div style={{ padding: "var(--space-6)", textAlign: "center" }}>
    <h1>404</h1>
    <p>Страница не найдена</p>
  </div>
);

export const AppRoutes = (): JSX.Element => {
  return (
    <Routes>
      <Route path={ROUTES.login} element={<LoginPage />} />

      <Route element={<PrivateRoute />}>
        <Route element={<AppShell />}>
          <Route element={<AdminRoute />}>
            <Route path={ROUTES.home} element={<Navigate to={ROUTES.dashboard} replace />} />
            <Route path={ROUTES.dashboard} element={<AttendanceDashboardPage />} />
            <Route path={ROUTES.attendanceEmployee} element={<EmployeeAttendancePage />} />
            <Route path={ROUTES.employees} element={<EmployeesListPage />} />
            <Route path={ROUTES.zones} element={<ZonesListPage />} />
            <Route path={ROUTES.radiomap} element={<RadiomapPage />} />
          </Route>
        </Route>
      </Route>

      <Route path={ROUTES.notFound} element={<NotFound />} />
    </Routes>
  );
};
