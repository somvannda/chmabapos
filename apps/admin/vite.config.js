import { defineConfig } from "vite";

export default defineConfig({
  base: "/admin/",
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
});
