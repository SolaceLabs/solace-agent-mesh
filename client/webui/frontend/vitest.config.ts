import { defineConfig, defineProject, mergeConfig } from "vitest/config";
import { playwright } from "@vitest/browser-playwright";

import { storybookTest } from "@storybook/addon-vitest/vitest-plugin";

import path from "node:path";
import { fileURLToPath } from "node:url";

const dirname = path.dirname(fileURLToPath(import.meta.url));

import viteConfig from "./vite.config";

export default mergeConfig(
    viteConfig({ mode: "DEVELOPMENT", command: "serve" }),
    defineConfig({
        test: {
            projects: [
                {
                    extends: true,
                    plugins: [
                        storybookTest({
                            configDir: path.join(dirname, ".storybook"),
                            storybookScript: "yarn storybook --no-open",
                        }),
                    ],
                    test: {
                        name: "storybook",
                        browser: {
                            enabled: true,
                            provider: playwright({}),
                            headless: true,
                            instances: [{ browser: "chromium" }],
                        },
                        setupFiles: ["./.storybook/vitest.setup.ts"],
                    },
                },
                defineProject({
                    test: {
                        name: "unit",
                        globals: true,
                        environment: "jsdom",
                        include: ["src/**/*.test.{ts,tsx}"],
                        setupFiles: ["./.storybook/vitest.setup.ts"],
                        alias: {
                            "@": path.resolve(dirname, "src"),
                        },
                    },
                }),
            ],
        },
    })
);
