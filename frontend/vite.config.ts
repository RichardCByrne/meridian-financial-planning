import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Split heavy third-party dependencies into their own chunks so the initial
// JS payload drops from ~1 MB to ~300 KB. recharts and firebase are the two
// biggest offenders; react-query + react-router are the remaining smaller
// vendor wins.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          recharts: ["recharts"],
          firebase: ["firebase/app", "firebase/auth"],
          "react-query": ["@tanstack/react-query"],
          router: ["react-router-dom"],
        },
      },
    },
  },
});
