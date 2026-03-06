import path from "path";
import fs from "fs";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

/**
 * Plugin that copies the pdf.worker.min.mjs file from pdfjs-dist into the
 * library dist/ output directory and resolves the ?url import to a stable
 * relative path.
 *
 * When building as a library (not an app), Vite does not process ?url imports
 * the same way — the worker URL ends up as undefined, breaking PDF rendering
 * in consumers like SAM Enterprise. This plugin ensures:
 *   1. The worker file is physically present in dist/ so consumers can serve it.
 *   2. The ?url import resolves to "./pdf.worker.min.mjs" (relative to dist/).
 */
function pdfWorkerLibPlugin(): Plugin {
    const WORKER_ID = "pdfjs-dist/build/pdf.worker.min.mjs";
    const WORKER_URL_ID = `${WORKER_ID}?url`;
    const WORKER_VIRTUAL_ID = "\0pdf-worker-url";
    const WORKER_FILENAME = "pdf.worker.min.mjs";

    return {
        name: "pdf-worker-lib",
        resolveId(id) {
            if (id === WORKER_URL_ID) {
                return WORKER_VIRTUAL_ID;
            }
        },
        load(id) {
            if (id === WORKER_VIRTUAL_ID) {
                // Return a stable relative URL that will be valid once the worker
                // file is copied into dist/ alongside index.js.
                return `export default "./${WORKER_FILENAME}";`;
            }
        },
        closeBundle() {
            // Copy the worker file from node_modules into dist/
            const workerSrc = path.resolve(__dirname, "node_modules/pdfjs-dist/build", WORKER_FILENAME);
            const workerDest = path.resolve(__dirname, "dist", WORKER_FILENAME);
            if (fs.existsSync(workerSrc)) {
                fs.copyFileSync(workerSrc, workerDest);
                console.log(`[pdf-worker-lib] Copied ${WORKER_FILENAME} to dist/`);
            } else {
                console.warn(`[pdf-worker-lib] Worker source not found: ${workerSrc}`);
            }
        },
    };
}

export default defineConfig({
    plugins: [react(), tailwindcss(), pdfWorkerLibPlugin()],
    build: {
        lib: {
            entry: path.resolve(__dirname, "src/lib/index.ts"),
            name: "SolaceAgentMeshUI",
            fileName: format => `index.${format === "es" ? "js" : "cjs"}`,
            formats: ["es", "cjs"],
        },
        outDir: "dist",
        rollupOptions: {
            // Make sure to externalize deps that shouldn't be bundled
            external: [
                "react",
                "react-dom",
                "react/jsx-runtime",
                "react-router-dom",
                "@radix-ui/react-accordion",
                "@radix-ui/react-avatar",
                "@radix-ui/react-dialog",
                "@radix-ui/react-popover",
                "@radix-ui/react-select",
                "@radix-ui/react-separator",
                "@radix-ui/react-slot",
                "@radix-ui/react-tabs",
                "@radix-ui/react-tooltip",
                "@tanstack/react-query",
                "@tanstack/react-table",
                "@xyflow/react",
                "class-variance-authority",
                "clsx",
                "dompurify",
                "html-react-parser",
                "js-yaml",
                "json-edit-react",
                "lucide-react",
                "marked",
                "radix-ui",
                "react-json-view-lite",
                "react-resizable-panels",
                "tailwind-merge",
                "tailwindcss",
            ],
            output: {
                // Global variables to use in UMD build for externalized deps
                globals: {
                    react: "React",
                    "react-dom": "ReactDOM",
                    "react/jsx-runtime": "jsxRuntime",
                },
            },
        },
        // Generate sourcemaps
        sourcemap: true,
        // Minify the output
        minify: true,
    },
    resolve: {
        alias: {
            "@": path.resolve(__dirname, "./src"),
        },
    },
});
