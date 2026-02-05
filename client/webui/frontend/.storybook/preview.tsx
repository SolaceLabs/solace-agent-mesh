import "../src/lib/index.css";
import "../src/App.css";

import type { Preview } from "@storybook/react-vite";
import { withProviders } from "../src/stories/decorators/withProviders";
import { withTheme } from "../src/stories/decorators/withTheme";
import { initialize, mswLoader } from "msw-storybook-addon";

initialize({
    onUnhandledRequest: "bypass",
    quiet: true,
});

const preview: Preview = {
    decorators: [withTheme, withProviders],

    loaders: [mswLoader],

    parameters: {
        actions: { argTypesRegex: "^on[A-Z].*" },

        controls: {
            matchers: {
                color: /(background|color)$/i,
                date: /Date$/i,
            },
            expanded: true,
        },
        layout: "centered",

        backgrounds: {
            default: "light",
            values: [
                {
                    name: "light",
                    value: "#ffffff",
                },
                {
                    name: "dark",
                    value: "#0a0a0a",
                },
            ],
        },
    },

    globalTypes: {
        theme: {
            description: "Global theme for components",
            defaultValue: "light",
            toolbar: {
                title: "Theme",
                icon: "circlehollow",
                items: ["light", "dark"],
                dynamicTitle: true,
            },
        },
    },
};

export default preview;
