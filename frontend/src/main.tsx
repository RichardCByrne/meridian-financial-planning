import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { App } from "./App";
import { AuthProvider } from "./auth/useAuth";
import { ConfirmDialogHost } from "./components/ConfirmDialog";
import { ToastProvider, emitToast } from "./components/Toast";
// Self-hosted brand fonts (bundled by Vite — no external CDN request).
// Bricolage Grotesque = display, Hanken Grotesk = body, IBM Plex Mono = figures.
import "@fontsource-variable/bricolage-grotesque/index.css";
import "@fontsource-variable/hanken-grotesk/index.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "@fontsource/ibm-plex-mono/latin-500.css";
import "./index.css";

function describeError(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  return "Something went wrong.";
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 5_000, refetchOnWindowFocus: false },
  },
  mutationCache: new MutationCache({
    onError: (err) => {
      emitToast({ kind: "error", message: `Save failed: ${describeError(err)}` });
    },
  }),
  queryCache: new QueryCache({
    onError: (err, query) => {
      // Suppress noise: only toast for top-level page loads, not background refetches.
      if (query.state.data !== undefined) return;
      emitToast({ kind: "error", message: `Couldn't load: ${describeError(err)}` });
    },
  }),
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <AuthProvider>
            <App />
            <ConfirmDialogHost />
          </AuthProvider>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
