import path from "path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, process.cwd(), "");

    const backendPort = env.VITE_BACKEND_PORT || process.env.FASTAPI_PORT || "8000";
    const backendTarget = `http://localhost:${backendPort}`;

    const enterprisePort = env.VITE_ENTERPRISE_PORT || "8001";
    const enterpriseTarget = `http://localhost:${enterprisePort}`;

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
                // IMPORTANT: Enterprise endpoints must come first for specificity
                // More specific routes must be defined before general routes
                "/api/v1/enterprise": {
                    target: enterpriseTarget,
                    changeOrigin: true,
                    secure: false,
                },
                // Community endpoints - catch-all for remaining /api routes
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
