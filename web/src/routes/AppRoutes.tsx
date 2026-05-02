import { Route, Routes } from "react-router-dom";

import { LoginPage } from "@/features/auth/LoginPage";
import { EmployeesListPage } from "@/features/employees/EmployeesListPage";
import { AppShell } from "@/layout/AppShell";

import { AdminRoute } from "./AdminRoute";
import { PrivateRoute } from "./PrivateRoute";
import { ROUTES } from "./routes";

const Placeholder = ({ title }: { title: string }): JSX.Element => (
  <div>
    <h1>{title}</h1>
    <p style={{ color: "var(--color-fg-muted)" }}>Страница в разработке.</p>
  </div>
);

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
            <Route path={ROUTES.home} element={<Placeholder title="Учёт времени" />} />
            <Route path={ROUTES.dashboard} element={<Placeholder title="Учёт времени" />} />
            <Route
              path={ROUTES.attendanceEmployee}
              element={<Placeholder title="Учёт сотрудника" />}
            />
            <Route path={ROUTES.employees} element={<EmployeesListPage />} />
            <Route path={ROUTES.zones} element={<Placeholder title="Зоны" />} />
            <Route path={ROUTES.radiomap} element={<Placeholder title="Радиокарта" />} />
          </Route>
        </Route>
      </Route>

      <Route path={ROUTES.notFound} element={<NotFound />} />
    </Routes>
  );
};
