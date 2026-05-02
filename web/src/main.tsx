import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { AuthExpiredError } from "./api/errors";
import { installInterceptors } from "./api/interceptors";
import { App } from "./App";
import "./index.css";
import { log } from "./lib/log";

log.info("[app.boot] start");

installInterceptors();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) =>
        !(error instanceof AuthExpiredError) && failureCount < 2,
    },
  },
});

const root = document.getElementById("root");
if (!root) throw new Error("Root element #root not found in index.html");

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
