// vite.config.ts
import { vitePlugin as remix } from "@remix-run/dev";
import { defineConfig } from "vite";
export default defineConfig({
  plugins: [
    remix({
      ssr: false,
      buildDirectory: "./static",
    }),
  ],
  server: {
    proxy: {
      // Proxy to main config_portal backend
      "/api": {
        target: "http://localhost:5002", // Config Portal backend URL
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/api/, "/api"),
      },
      // Proxy to wizard Flask server
      "/wizard_api": {
        target: "http://localhost:5005", // Wizard backend URL
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/wizard_api/, "/api"),
      },
    },
  },
});