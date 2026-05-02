import { ChartBar, MapPin, Tag, Users } from "lucide-react";
import { NavLink } from "react-router-dom";

import { ROUTES } from "@/routes/routes";

const navItem = (active: boolean): React.CSSProperties => ({
  display: "flex",
  alignItems: "center",
  gap: "var(--space-3)",
  padding: "var(--space-3) var(--space-4)",
  color: active ? "var(--color-primary)" : "var(--color-fg)",
  background: active ? "var(--color-surface-muted)" : "transparent",
  borderLeft: active
    ? "3px solid var(--color-primary)"
    : "3px solid transparent",
  textDecoration: "none",
  fontSize: 14,
});

export const Sidebar = (): JSX.Element => {
  return (
    <nav
      style={{
        height: "100%",
        background: "var(--color-surface)",
        borderRight: "1px solid var(--color-border)",
        paddingTop: "var(--space-4)",
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-1)",
      }}
    >
      <NavLink to={ROUTES.dashboard} style={({ isActive }) => navItem(isActive)}>
        <ChartBar size={18} />
        <span>Учёт времени</span>
      </NavLink>
      <NavLink to={ROUTES.employees} style={({ isActive }) => navItem(isActive)}>
        <Users size={18} />
        <span>Сотрудники</span>
      </NavLink>
      <NavLink to={ROUTES.zones} style={({ isActive }) => navItem(isActive)}>
        <Tag size={18} />
        <span>Зоны</span>
      </NavLink>
      <NavLink to={ROUTES.radiomap} style={({ isActive }) => navItem(isActive)}>
        <MapPin size={18} />
        <span>Радиокарта</span>
      </NavLink>
    </nav>
  );
};
