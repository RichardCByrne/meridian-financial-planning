import { useState } from "react";
import { useLocation, useNavigate, Navigate } from "react-router-dom";
import { FirebaseError } from "firebase/app";
import {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signInWithPopup,
} from "firebase/auth";

import { DEV_AUTH, firebaseAuth, googleProvider } from "../auth/firebaseConfig";
import { useAuth } from "../auth/useAuth";

const GENERIC_SIGNIN_ERROR =
  "Sign in failed. Please check your email and password and try again.";
const GENERIC_SIGNUP_ERROR = "We couldn't create your account. Please try again.";

// Map a Firebase auth error to a user-facing message. Deliberately generic for
// anything that could reveal whether an account exists or which credential was
// wrong (user-not-found / wrong-password / invalid-credential / user-disabled /
// email-already-in-use) — exposing those enables account enumeration. Only
// input/transport problems that leak nothing get a specific, helpful message.
// Returns null when there's nothing worth showing (user dismissed the popup).
function friendlyAuthError(err: unknown, mode: "signin" | "signup"): string | null {
  const code = err instanceof FirebaseError ? err.code : "";
  switch (code) {
    case "auth/popup-closed-by-user":
    case "auth/cancelled-popup-request":
      return null;
    case "auth/invalid-email":
      return "Please enter a valid email address.";
    case "auth/weak-password":
      return "Choose a password of at least 6 characters.";
    case "auth/too-many-requests":
      return "Too many attempts. Please wait a moment and try again.";
    case "auth/network-request-failed":
      return "Network error. Check your connection and try again.";
    default:
      return mode === "signup" ? GENERIC_SIGNUP_ERROR : GENERIC_SIGNIN_ERROR;
  }
}

export function LoginPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  // Honour `state.from` (set by ProtectedRoute) first, then fall back to the
  // `?next=` query param which is used when the API client triggers a full
  // page reload via window.location.assign on a 401 response.
  const queryNext = new URLSearchParams(location.search).get("next");
  const fromPath =
    (location.state as { from?: string } | null)?.from ?? queryNext ?? "/plans";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (auth.status === "signed-in") return <Navigate to={fromPath} replace />;

  if (DEV_AUTH) {
    return (
      <div className="card" style={{ maxWidth: 480 }}>
        <h2>Sign in</h2>
        <p className="muted">
          The app is running in <strong>dev-auth mode</strong> (<code>VITE_DEV_AUTH=true</code>);
          a local-only "dev" user is signed in automatically. To enable Firebase Auth, set
          <code> VITE_DEV_AUTH=false</code> and configure the <code>VITE_FIREBASE_*</code>
          environment variables. See README §"Firebase setup" for details.
        </p>
      </div>
    );
  }

  const onGoogle = async () => {
    setError(null);
    setBusy(true);
    try {
      await signInWithPopup(firebaseAuth(), googleProvider);
      navigate(fromPath, { replace: true });
    } catch (e) {
      setError(friendlyAuthError(e, "signin"));
    } finally {
      setBusy(false);
    }
  };

  const onEmailPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "signin") {
        await signInWithEmailAndPassword(firebaseAuth(), email, password);
      } else {
        await createUserWithEmailAndPassword(firebaseAuth(), email, password);
      }
      navigate(fromPath, { replace: true });
    } catch (err) {
      setError(friendlyAuthError(err, mode));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 420 }}>
      <h2>Sign in to Meridian</h2>
      <div className="card">
        <button
          className="btn"
          onClick={onGoogle}
          disabled={busy}
          style={{ width: "100%", marginBottom: 16 }}
        >
          Continue with Google
        </button>
        <hr style={{ border: 0, borderTop: "1px solid #e2e8f0", margin: "16px 0" }} />
        <form onSubmit={onEmailPassword}>
          <div className="field">
            <label htmlFor="login-email">Email</label>
            <input
              id="login-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="login-password">Password</label>
            <input
              id="login-password"
              type="password"
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={6}
              required
            />
          </div>
          <button className="btn" type="submit" disabled={busy} style={{ width: "100%" }}>
            {busy ? "…" : mode === "signin" ? "Sign in" : "Create account"}
          </button>
        </form>
        <p style={{ marginTop: 16, fontSize: 13 }}>
          {mode === "signin" ? "New here? " : "Already have an account? "}
          <button
            type="button"
            onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
            style={{ background: "none", border: 0, color: "#2563eb", cursor: "pointer", padding: 0 }}
          >
            {mode === "signin" ? "Create account" : "Sign in"}
          </button>
        </p>
        {error && <p style={{ color: "#dc2626", fontSize: 13 }}>{error}</p>}
      </div>
    </div>
  );
}
