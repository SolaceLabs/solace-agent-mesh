import React from "react";

import { MockAuthProvider } from "./MockAuthProvider";
import { MockTaskProvider } from "./MockTaskProvider";
import { MockConfigProvider } from "./MockConfigProvider";
import type { AuthContextValue } from "@/lib/contexts/AuthContext";
import { ThemeProvider, type ChatContextValue, type ConfigContextValue, type TaskContextValue } from "@/lib";
import { MockChatProvider } from "./MockChatProvider";

interface RouterValues {
    initialPath?: string;
    routePath?: string;
}

interface StoryProviderProps {
    children: React.ReactNode;
    authContextValues?: Partial<AuthContextValue>;
    chatContextValues?: Partial<ChatContextValue>;
    taskContextValues?: Partial<TaskContextValue>;
    configContextValues?: Partial<ConfigContextValue>;
    routerValues?: RouterValues;
}

/**
 * A shared provider component that combines all necessary context providers for stories.
 * This makes it easy to provide consistent mock context across all Storybook tests.
 *
 * It now also supports React Router context for stories that need routing capabilities.
 *
 * Usage:
 * ```
 * <StoryProvider
 *   chatContextValues={{ ... }}
 *   routerValues={{
 *     initialPath: '/agents/123',
 *     routePath: '/agents/:id'
 *   }}
 * >
 *   <YourComponent />
 * </StoryProvider>
 * ```
 */
export const StoryProvider: React.FC<StoryProviderProps> = ({ children, authContextValues = {}, chatContextValues = {}, taskContextValues = {}, configContextValues = {} }) => {
    const content = (
        <ThemeProvider>
            <MockConfigProvider mockValues={configContextValues}>
                <MockAuthProvider mockValues={authContextValues}>
                    <MockTaskProvider mockValues={taskContextValues}>
                        <MockChatProvider mockValues={chatContextValues}>{children}</MockChatProvider>
                    </MockTaskProvider>
                </MockAuthProvider>
            </MockConfigProvider>
        </ThemeProvider>
    );

    return content;
};
