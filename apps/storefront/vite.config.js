import { reactRouter } from "@react-router/dev/vite";
import { defineConfig, loadEnv } from "vite";

// In production the storefront host terminates TLS and proxies /api and /media to
// the API container, so the browser always talks to its own origin. This dev
// proxy mirrors that exactly.
//
// It is not a convenience: without it the browser would call the API
// cross-origin and every request would be refused by CORS, because the API's
// allowed origins do not include the storefront's dev port. Mirroring the
// deployed shape keeps development honest and means no CORS configuration is
// needed to work on the storefront at all.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = env.VITE_DEV_API_TARGET || "http://127.0.0.1:8000";
  return {
    plugins: [reactRouter()],
    // The shared chrome in packages/ui has no node_modules of its own, so React is
    // resolved from this app for any module under it.
    resolve: {
      dedupe: ["react", "react-dom", "react/jsx-runtime", "react-dom/client"],
    },
    server: {
      // packages/ui (the shared chrome, alongside tokens.css) sits outside this
      // app's root.
      fs: { allow: ["../.."] },
      proxy: {
        "/api": { target: apiTarget, changeOrigin: true },
        "/media": { target: apiTarget, changeOrigin: true },
      },
    },
  };
});
