import path from "path";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(async ({ mode }) => {
    const env = loadEnv(mode, process.cwd(), "");

    const backendPort = env.VITE_BACKEND_PORT || process.env.FASTAPI_PORT || "8000";
    const backendTarget = `http://127.0.0.1:${backendPort}`;

    // Dynamic import for ESM-only package
    const { default: tailwindcss } = await import("@tailwindcss/vite");

    return {
        plugins: [react(), tailwindcss()],
        resolve: {
            alias: {
                "@": path.resolve(__dirname, "./src"),
            },
        },
        build: {
            outDir: "static",
            emptyOutDir: true,
            rollupOptions: {
                input: {
                    main: "index.html",
                    authCallback: "auth-callback.html",
                },
                output: {
                    manualChunks: {
                        vendor: ["react", "react-dom", "recharts", "@xyflow/react", "json-edit-react", "marked", "@tanstack/react-table", "lucide-react", "html-react-parser"],
                    },
                },
            },
        },
        server: {
            proxy: {
                "/api": {
                    target: backendTarget,
                    changeOrigin: true,
                    secure: false,
                },
            },
            port: 3000, // Explicitly set frontend dev server port (optional)
            host: true, // Allow access from network (optional)
        },
    };
});
