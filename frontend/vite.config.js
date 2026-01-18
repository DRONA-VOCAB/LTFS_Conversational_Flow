import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Backend API URL from environment variable or default
const BACKEND_URL = process.env.VITE_API_URL || "http://localhost:8001";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: BACKEND_URL,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
