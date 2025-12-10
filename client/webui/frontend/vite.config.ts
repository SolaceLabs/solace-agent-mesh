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
                    ws: true, // Support WebSocket proxying for HMR
                    autoRewrite: true, // Rewrite location headers
                    protocolRewrite: 'http', // Force http protocol in rewrites
                    // Ensure we don't bypass the proxy for any /api requests
                    bypass: (req, _res, _options) => {
                        const shouldProxy = req.url?.startsWith('/api');
                        console.log(`[Vite Proxy] ${req.method} ${req.url} -> ${shouldProxy ? 'PROXY' : 'BYPASS'}`);
                        // Return null to proxy, return anything else to bypass
                        return shouldProxy ? null : undefined;
                    },
                    configure: (proxy, _options) => {
                        proxy.on('error', (err, _req, _res) => {
                            console.log('[Vite Proxy] ERROR:', err);
                        });
                        proxy.on('proxyReq', (proxyReq, req, _res) => {
                            console.log('[Vite Proxy] Proxying:', req.method, req.url, '->', backendTarget + req.url);
                        });
                        proxy.on('proxyRes', (proxyRes, req, _res) => {
                            console.log('[Vite Proxy] Proxied:', req.method, req.url, '-> Status:', proxyRes.statusCode);
                        });
                    },
                },
            },
            port: 3000,
            host: true,
        },
    };
});
