import type { Decorator, StoryFn, StoryContext } from "@storybook/react";
import { StoryProvider } from "../mocks/StoryProvider";
import { createMemoryRouter, RouterProvider } from "react-router-dom";

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
    const authContextValues = {
        ...(context.parameters.authContext || {}),
        ...(context.args.authContext || {}),
    };

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

    const projectContextValues = {
        ...(context.parameters.projectContext || {}),
        ...(context.args.projectContext || {}),
    };

    // Always provide router context with sensible defaults
    const routerValues = {
        initialPath: "/",
        routePath: "/*",
        ...(context.parameters.routerValues || {}),
        ...(context.args.routerValues || {}),
    };

    const router = createMemoryRouter([
        {
            path: "*",
            element: (
                <StoryProvider
                    authContextValues={authContextValues}
                    chatContextValues={chatContextValues}
                    taskContextValues={taskContextValues}
                    configContextValues={configContextValues}
                    projectContextValues={projectContextValues}
                    routerValues={routerValues}
                >
                    <div style={{ height: "100vh", width: "100vw" }}>{Story(context.args, context)}</div>
                </StoryProvider>
            ),
        },
    ]);

    return <RouterProvider router={router} />;
};
