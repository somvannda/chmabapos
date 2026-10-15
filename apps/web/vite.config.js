import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = env.VITE_DEV_API_TARGET || "http://127.0.0.1:8000";
  return {
    build: {
      chunkSizeWarningLimit: 700,
      rolldownOptions: {
        output: {
          manualChunks(id) {
            if (id.includes("node_modules/react") || id.includes("node_modules/react-dom") || id.includes("node_modules/scheduler")) return "react";
            if (id.includes("node_modules/lucide-react")) return "icons";
            if (id.includes("node_modules/qrcode.react")) return "qr";
            return undefined;
          },
        },
      },
    },
    // packages/ui/chrome.jsx sits outside this app and has no node_modules of its
    // own, so React must be resolved from here or the bundler cannot find
    // react/jsx-runtime at all.
    resolve: {
      dedupe: ["react", "react-dom", "react/jsx-runtime", "react-dom/client"],
    },
    server: {
      // The shared marketing chrome lives in packages/ui, outside this app's root,
      // so the dev server has to be allowed to serve it.
      fs: { allow: ["../.."] },
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
        },
        "/media": {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
