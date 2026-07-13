import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/api/agent": {
        target: "http://127.0.0.1:8095",
        changeOrigin: true,
      },
      "/api/workflow": {
        target: "http://127.0.0.1:8093",
        changeOrigin: true,
      },
      "/api": {
        target: "http://127.0.0.1:8092",
        changeOrigin: true,
      },
      "/health": {
        target: "http://127.0.0.1:8092",
        changeOrigin: true,
      },
    },
  },
});
