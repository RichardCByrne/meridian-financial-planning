import { useEffect, useState } from "react";
import { Link, NavLink, Route, Routes, Navigate, useLocation } from "react-router-dom";

import { ProtectedRoute } from "./auth/ProtectedRoute";
import { useAuth } from "./auth/useAuth";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { TourProvider, useTour } from "./components/GuidedTour";
import { AcceptInvitePage } from "./pages/AcceptInvitePage";
import { GuidePage } from "./pages/GuidePage";
import { LoginPage } from "./pages/LoginPage";
import { PlansListPage } from "./pages/PlansList";
import { PlanEditorPage } from "./pages/PlanEditor";
import { PlanWizardPage } from "./pages/PlanWizardPage";

export function App() {
  return (
    <TourProvider>
      <AppShell />
    </TourProvider>
  );
}

function AppShell() {
  const tour = useTour();
  const auth = useAuth();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  // Logo goes home: the plans list when signed in, the login screen otherwise.
  const brandTarget = auth.status === "signed-in" ? "/plans" : "/login";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <Link
            to={brandTarget}
            aria-label="Meridian home"
            style={{ textDecoration: "none", color: "inherit" }}
          >
            <h1 className="brand">
              <span className="brand-mark" aria-hidden />
              <span>Meridian</span>
            </h1>
          </Link>
          <button
            type="button"
            className="sidebar-toggle"
            aria-expanded={menuOpen}
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            onClick={() => setMenuOpen((o) => !o)}
          >
            {menuOpen ? "✕" : "☰"}
          </button>
        </div>
        <div className={"sidebar-menu" + (menuOpen ? " open" : "")}>
          <nav>
            <NavLink to="/plans" className={({ isActive }) => (isActive ? "active" : "")}>
              Plans
            </NavLink>
            <NavLink to="/guide" className={({ isActive }) => (isActive ? "active" : "")}>
              Guide
            </NavLink>
            <button
              type="button"
              onClick={() => {
                setMenuOpen(false);
                tour.start();
              }}
              style={{
                display: "block",
                width: "100%",
                padding: "8px 12px",
                border: "1px solid var(--ink-soft)",
                background: "transparent",
                color: "#cbd5e1",
                borderRadius: "var(--radius-sm)",
                marginTop: 8,
                fontSize: 13,
                textAlign: "left",
                cursor: "pointer",
              }}
            >
              ✨ Take the tour
            </button>
          </nav>
          <UserChip />
          <p className="muted" style={{ marginTop: 16, color: "#94a3b8", fontSize: 12 }}>
            Ireland 2026 tax engine · v0.8
          </p>
        </div>
      </aside>
      <main className="main">
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<Navigate to="/plans" replace />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/invites/:token" element={<AcceptInvitePage />} />
            <Route
              path="/guide"
              element={
                <ProtectedRoute>
                  <GuidePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/plans"
              element={
                <ProtectedRoute>
                  <PlansListPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/plans/new"
              element={
                <ProtectedRoute>
                  <PlanWizardPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/plans/new/:stepId"
              element={
                <ProtectedRoute>
                  <PlanWizardPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/plans/:planId/*"
              element={
                <ProtectedRoute>
                  <PlanEditorPage />
                </ProtectedRoute>
              }
            />
          </Routes>
        </ErrorBoundary>
      </main>
    </div>
  );
}

function UserChip() {
  const auth = useAuth();
  if (auth.status !== "signed-in") return null;
  const label = auth.user.displayName || auth.user.email || "Signed in";
  return (
    <div
      style={{
        marginTop: 24,
        padding: "10px 12px",
        background: "var(--ink-soft)",
        borderRadius: "var(--radius-sm)",
        fontSize: 12,
        color: "#cbd5e1",
      }}
    >
      <div style={{ fontWeight: 600, color: "#f8fafc", marginBottom: 4 }}>{label}</div>
      {auth.user.email && auth.user.email !== label && (
        <div style={{ fontSize: 11, marginBottom: 6 }}>{auth.user.email}</div>
      )}
      <button
        onClick={() => auth.signOut()}
        style={{
          background: "transparent",
          border: "1px solid #475569",
          color: "#cbd5e1",
          padding: "4px 8px",
          borderRadius: 4,
          fontSize: 11,
          cursor: "pointer",
          width: "100%",
        }}
      >
        Sign out
      </button>
    </div>
  );
}
