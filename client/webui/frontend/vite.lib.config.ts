import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
    plugins: [react(), tailwindcss()],
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
