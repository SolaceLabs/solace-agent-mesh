import type { Preview } from "@storybook/react-vite";
import "../src/lib/index.css";

const preview: Preview = {
    parameters: {
        actions: { argTypesRegex: "^on[A-Z].*" },
        controls: {
            matchers: {
                color: /(background|color)$/i,
                date: /Date$/i,
            },
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
