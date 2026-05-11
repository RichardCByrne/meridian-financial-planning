import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { onAuthStateChanged, signOut, type User as FirebaseUser } from "firebase/auth";

import { DEV_AUTH, firebaseAuth } from "./firebaseConfig";

export type AuthUser = {
  uid: string;
  email: string | null;
  displayName: string | null;
  // Returns a fresh ID token for the Authorization header. In dev mode the
  // backend ignores the value, but we send a sentinel anyway so the wire
  // format is identical.
  getIdToken(forceRefresh?: boolean): Promise<string>;
};

type AuthState =
  | { status: "loading"; user: null }
  | { status: "signed-out"; user: null }
  | { status: "signed-in"; user: AuthUser };

type AuthContextValue = AuthState & {
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const DEV_USER: AuthUser = {
  uid: "dev-local",
  email: "dev@meridian.local",
  displayName: "Local Dev User",
  getIdToken: async () => "dev-token",
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(
    DEV_AUTH ? { status: "signed-in", user: DEV_USER } : { status: "loading", user: null }
  );

  useEffect(() => {
    if (DEV_AUTH) {
      setCurrentUserForApi(DEV_USER);
      return;
    }
    const auth = firebaseAuth();
    const unsub = onAuthStateChanged(auth, (fbUser: FirebaseUser | null) => {
      if (fbUser) {
        const user: AuthUser = {
          uid: fbUser.uid,
          email: fbUser.email,
          displayName: fbUser.displayName,
          getIdToken: (force) => fbUser.getIdToken(force),
        };
        setCurrentUserForApi(user);
        setState({ status: "signed-in", user });
      } else {
        setCurrentUserForApi(null);
        setState({ status: "signed-out", user: null });
      }
    });
    return () => unsub();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      signOut: async () => {
        if (DEV_AUTH) {
          // No-op in dev mode — there's nothing to sign out of.
          return;
        }
        await signOut(firebaseAuth());
      },
    }),
    [state]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be called inside <AuthProvider>");
  return ctx;
}

// Module-level helper so non-React code (the API client) can grab a token.
let _currentUser: AuthUser | null = DEV_AUTH ? DEV_USER : null;
export function setCurrentUserForApi(user: AuthUser | null) {
  _currentUser = user;
}
export function getCurrentUserForApi(): AuthUser | null {
  return _currentUser;
}
