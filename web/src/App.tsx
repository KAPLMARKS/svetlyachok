import { env } from "./lib/env";

export const App = (): JSX.Element => {
  return (
    <main
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100vh",
        gap: "var(--space-3)",
      }}
    >
      <h1>Светлячок</h1>
      <p>Админ-панель — scaffold готов.</p>
      <code style={{ background: "var(--color-surface)", padding: "var(--space-2) var(--space-3)" }}>
        API base URL: {env.apiBaseUrl}
      </code>
    </main>
  );
};
