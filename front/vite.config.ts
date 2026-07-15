import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      // AgentScope create_app（langgraph_bridge_app.py :8000）
      "/chat": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/sessions": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/agent": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/credential": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/model": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/tts-model": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/schedule": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/knowledge_bases": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/workspace": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/docs": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/openapi.json": { target: "http://127.0.0.1:8000", changeOrigin: true },
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
