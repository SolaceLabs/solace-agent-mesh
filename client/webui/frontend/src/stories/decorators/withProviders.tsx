import type { Decorator, StoryFn, StoryContext } from "@storybook/react";
import { StoryProvider } from "../mocks/StoryProvider";

/**
 * A Storybook decorator that wraps stories with all necessary context providers.
 *
 * Usage:
 * 1. Apply globally in preview.js:
 *    ```
 *    export const decorators = [withProviders];
 *    ```
 *
 * 2. Or apply to specific stories:
 *    ```
 *    export default {
 *      decorators: [withProviders],
 *      // ...
 *    };
 *    ```
 *
 * 3. Provide context values in story parameters or args:
 *    ```
 *    export const MyStory = {
 *      parameters: {
 *        chatContext: { ... },
 *        taskContext: { ... },
 *        configContext: { ... },
 *      },
 *    };
 *    ```
 */
export const withProviders: Decorator = (Story: StoryFn, context: StoryContext) => {
    // Extract mock values from story parameters or args
    const chatContextValues = {
        ...(context.parameters.chatContext || {}),
        ...(context.args.chatContext || {}),
    };

    const taskContextValues = {
        ...(context.parameters.taskContext || {}),
        ...(context.args.taskContext || {}),
    };

    const configContextValues = {
        ...(context.parameters.configContext || {}),
        ...(context.args.configContext || {}),
    };

    const storyResult = Story(context.args, context);

    return (
        <StoryProvider chatContextValues={chatContextValues} taskContextValues={taskContextValues} configContextValues={configContextValues}>
            {storyResult}
        </StoryProvider>
    );
};
