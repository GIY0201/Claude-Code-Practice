import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import cesium from "vite-plugin-cesium";
import path from "path";

const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
const backendWs = backendUrl.replace(/^http/, "ws");

export default defineConfig({
  plugins: [react(), tailwindcss(), cesium()],
  resolve: {
    dedupe: ["react", "react-dom"],
    alias: {
      react: path.resolve("./node_modules/react"),
      "react-dom": path.resolve("./node_modules/react-dom"),
      "react/jsx-runtime": path.resolve("./node_modules/react/jsx-runtime"),
      "react/jsx-dev-runtime": path.resolve("./node_modules/react/jsx-dev-runtime"),
    },
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/api": {
        target: backendUrl,
        changeOrigin: true,
      },
      "/ws": {
        target: backendWs,
        ws: true,
      },
    },
  },
});
