import "../src/lib/index.css";
import "../src/App.css";

import type { Preview } from "@storybook/react-vite";
import { withProviders } from "../src/stories/decorators/withProviders";
import { initialize, mswLoader } from "msw-storybook-addon";

initialize({
    onUnhandledRequest: "bypass",
    quiet: true,
});

const preview: Preview = {
    decorators: [withProviders],

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
    },
};

export default preview;
