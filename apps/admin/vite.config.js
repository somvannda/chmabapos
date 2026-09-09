import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = env.VITE_DEV_API_TARGET || "http://127.0.0.1:8000";
  return {
    base: "/",
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
    server: {
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
