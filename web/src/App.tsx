import { useEffect } from "react";
import { Toaster } from "react-hot-toast";
import { BrowserRouter } from "react-router-dom";

import { useAuthStore } from "./features/auth/authStore";
import { AppRoutes } from "./routes/AppRoutes";

export const App = (): JSX.Element => {
  const bootstrap = useAuthStore((s) => s.bootstrapFromRefresh);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  return (
    <BrowserRouter>
      <AppRoutes />
      <Toaster position="top-right" />
    </BrowserRouter>
  );
};
