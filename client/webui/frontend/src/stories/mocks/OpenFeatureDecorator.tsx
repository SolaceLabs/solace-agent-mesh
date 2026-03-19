import React from "react";
import { OpenFeature, OpenFeatureProvider } from "@openfeature/react-sdk";
import { SamFeatureProvider } from "@/lib/providers/openfeature";

interface OpenFeatureDecoratorOptions {
    flags?: Record<string, boolean>;
}

/**
 * Shared decorator to provide OpenFeature context in Storybook stories.
 * Initializes the feature provider with the given flags.
 */
export function createOpenFeatureDecorator(options: OpenFeatureDecoratorOptions = {}) {
    const { flags = {} } = options;

    // Initialize OpenFeature
    const initializeOpenFeature = async () => {
        const provider = new SamFeatureProvider(flags);
        await OpenFeature.setProviderAndWait(provider);
    };

    initializeOpenFeature().catch(console.error);

    return (Story: React.ComponentType) => (
        <OpenFeatureProvider>
            <Story />
        </OpenFeatureProvider>
    );
}
