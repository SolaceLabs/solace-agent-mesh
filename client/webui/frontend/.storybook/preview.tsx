import React from "react";
import "../src/lib/index.css";
import "../src/App.css";

import type { Preview } from "@storybook/react-vite";
import { ThemeProvider } from "../src/lib/providers/ThemeProvider";
import { withProviders } from "../src/stories/decorators/withProviders";

const preview: Preview = {
    decorators: [withProviders],
    parameters: {
        actions: { argTypesRegex: "^on[A-Z].*" },

        controls: {
            matchers: {
                color: /(background|color)$/i,
                date: /Date$/i,
            },
            expanded: true,
        },
        backgrounds: {
            default: "light",
            values: [
                {
                    name: "light",
                    value: "#ffffff",
                },
                {
                    name: "dark",
                    value: "#1a1a1a",
                },
            ],
        },
        layout: "centered",
    },
};

export default preview;
