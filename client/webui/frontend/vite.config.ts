import path from "path";
import fs from "fs";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

/**
 * Local Vite plugin to generate ui-version.json during build.
 * This metadata file contains version information that can be read at runtime
 * without exposing the full package.json.
 */
function generateVersionMetadata() {
    return {
        name: "generate-version-metadata",
        closeBundle() {
            const packageJsonPath = path.resolve(__dirname, "package.json");
            const outputPath = path.resolve(__dirname, "static", "ui-version.json");

            try {
                const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, "utf-8"));
                const versionMetadata = {
                    id: packageJson.name,
                    name: "Solace Agent Mesh UI",
                    description: packageJson.description || "",
                    version: packageJson.version,
                };

                // Ensure output directory exists before writing
                const outputDir = path.dirname(outputPath);
                if (!fs.existsSync(outputDir)) {
                    fs.mkdirSync(outputDir, { recursive: true });
                }

                fs.writeFileSync(outputPath, JSON.stringify(versionMetadata, null, 2) + "\n");
                console.log(`Generated ui-version.json: ${versionMetadata.version}`);
            } catch (error) {
                console.error("Failed to generate ui-version.json:", error);
            }
        },
    };
}

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, process.cwd(), "");

    const backendPort = env.VITE_BACKEND_PORT || process.env.FASTAPI_PORT || "8000";
    const backendTarget = `http://localhost:${backendPort}`;

    const platformPort = env.VITE_PLATFORM_PORT || "8001";
    const platformTarget = `http://localhost:${platformPort}`;

    return {
        plugins: [react(), tailwindcss(), generateVersionMetadata()],
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
                        vendor: ["react", "react-dom", "json-edit-react", "marked", "@tanstack/react-table", "lucide-react", "html-react-parser"],
                    },
                },
            },
        },
        server: {
            proxy: {
                // IMPORTANT: Platform Service endpoints must come first for specificity
                // More specific routes must be defined before general routes
                "/api/v1/platform": {
                    target: platformTarget,
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
