// This file has been automatically migrated to valid ESM format by Storybook.
import { fileURLToPath } from "node:url";
import type { StorybookConfig } from "@storybook/react-vite";
import path, { dirname } from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const config: StorybookConfig = {
    stories: ["../src/**/*.mdx", "../src/**/*.stories.@(js|jsx|mjs|ts|tsx)"],
    addons: ["@storybook/addon-vitest"],
    framework: {
        name: "@storybook/react-vite",
        options: {},
    },
    core: {
        disableTelemetry: true,
    },
    staticDirs: ["../public", "../src/assets/"],
    viteFinal: async config => {
        // Add path aliases to match the project configuration
        if (config.resolve) {
            config.resolve.alias = {
                ...config.resolve.alias,
                "@": path.resolve(__dirname, "../src"),
            };
        }
        return config;
    },
};
export default config;
