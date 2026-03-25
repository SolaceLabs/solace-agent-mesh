import React from "react";
import { OpenFeatureTestProvider } from "@openfeature/react-sdk";

interface OpenFeatureDecoratorOptions {
    flags?: Record<string, boolean>;
}

export function createOpenFeatureDecorator(options: OpenFeatureDecoratorOptions = {}) {
    return (Story: React.ComponentType) => (
        <OpenFeatureTestProvider flagValueMap={options.flags ?? {}}>
            <Story />
        </OpenFeatureTestProvider>
    );
}
