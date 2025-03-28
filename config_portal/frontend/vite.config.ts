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
      "/api": {
        target: "http://localhost:5002", // Go backend URL
        changeOrigin: true,
        secure: false, // Disable SSL verification if not using HTTPS
        rewrite: (path) => path.replace(/^\/api/, "/api"),
      },
    },
  },
});