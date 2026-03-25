import type { Decorator, StoryFn, StoryContext } from "@storybook/react";
import { OpenFeatureTestProvider } from "@openfeature/react-sdk";

interface OpenFeatureDecoratorOptions {
    flags?: Record<string, boolean>;
}

export function createOpenFeatureDecorator(options: OpenFeatureDecoratorOptions = {}): Decorator {
    return (Story: StoryFn, context: StoryContext) => <OpenFeatureTestProvider flagValueMap={options.flags ?? {}}>{Story(context.args, context)}</OpenFeatureTestProvider>;
}
