import { Outlet } from "react-router-dom";

import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export const AppShell = (): JSX.Element => {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "var(--sidebar-width) 1fr",
        gridTemplateRows: "var(--topbar-height) 1fr",
        gridTemplateAreas: "'topbar topbar' 'sidebar content'",
        minHeight: "100vh",
        background: "var(--color-bg)",
      }}
    >
      <header style={{ gridArea: "topbar" }}>
        <Topbar />
      </header>
      <aside style={{ gridArea: "sidebar" }}>
        <Sidebar />
      </aside>
      <main style={{ gridArea: "content", padding: "var(--space-5)", overflow: "auto" }}>
        <Outlet />
      </main>
    </div>
  );
};
