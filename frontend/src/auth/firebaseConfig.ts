import { initializeApp, type FirebaseApp } from "firebase/app";
import {
  EmailAuthProvider,
  GoogleAuthProvider,
  getAuth,
  type Auth,
} from "firebase/auth";

// `VITE_DEV_AUTH=true` (the default for local dev) skips Firebase entirely and
// pretends the user is signed in as the seeded backend dev user. The backend's
// `MERIDIAN_DEV_AUTH` flag must match.
export const DEV_AUTH = import.meta.env.VITE_DEV_AUTH !== "false";

const config = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

let _app: FirebaseApp | null = null;
let _auth: Auth | null = null;

export function firebaseAuth(): Auth {
  if (DEV_AUTH) {
    throw new Error("Firebase auth is not initialised in dev mode (VITE_DEV_AUTH=true)");
  }
  if (_auth) return _auth;
  if (!config.apiKey || !config.projectId) {
    throw new Error(
      "Firebase config missing. Set VITE_FIREBASE_* env vars or VITE_DEV_AUTH=true."
    );
  }
  _app = initializeApp(config);
  _auth = getAuth(_app);
  return _auth;
}

export const googleProvider = new GoogleAuthProvider();
export const emailProvider = EmailAuthProvider;
