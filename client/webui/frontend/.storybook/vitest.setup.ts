import { setProjectAnnotations } from "@storybook/react-vite";
import * as projectAnnotations from "./preview";

// Official workaround for "TypeError: window.matchMedia is not a function"
// https://jestjs.io/docs/manual-mocks#mocking-methods-which-are-not-implemented-in-jsdom
Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: any) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: () => {}, // deprecated
        removeListener: () => {}, // deprecated
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => {},
    }),
});

// Polyfill Blob.prototype.text for older jsdom versions
if (typeof Blob.prototype.text === "undefined") {
    Object.defineProperty(Blob.prototype, "text", {
        value: function (this: Blob) {
            return new Promise<string>((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result as string);
                reader.onerror = () => reject(reader.error);
                reader.readAsText(this);
            });
        },
    });
}

// Polyfill ResizeObserver for JSDOM (used by @radix-ui/react-use-size)
if (typeof globalThis.ResizeObserver === "undefined") {
    globalThis.ResizeObserver = class ResizeObserver {
        observe() {}
        unobserve() {}
        disconnect() {}
    } as any;
}

// This is an important step to apply the right configuration when testing your stories.
// More info at: https://storybook.js.org/docs/api/portable-stories/portable-stories-vitest#setprojectannotations
setProjectAnnotations([projectAnnotations]);
