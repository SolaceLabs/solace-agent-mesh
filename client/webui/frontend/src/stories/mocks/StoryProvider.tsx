import React from "react";

import { MockAuthProvider } from "./MockAuthProvider";
import { MockTaskProvider } from "./MockTaskProvider";
import { MockConfigProvider } from "./MockConfigProvider";
import type { AuthContextValue } from "@/lib/contexts/AuthContext";
import { ThemeProvider, type AudioSettingsContextValue, type ChatContextValue, type ConfigContextValue, type SelectionContextValue, type TaskContextValue } from "@/lib";
import { MockChatProvider } from "./MockChatProvider";
import { MockProjectProvider } from "./MockProjectProvider";
import type { ProjectContextValue } from "@/lib/types/projects";
import { MockTextSelectionProvider } from "./MockTextSelectionProvider";
import { MockAudioSettingsProvider } from "./MockAudioSettingsProvider";

interface RouterValues {
    initialPath?: string;
    routePath?: string;
}

interface StoryProviderProps {
    children: React.ReactNode;
    authContextValues?: Partial<AuthContextValue>;
    chatContextValues?: Partial<ChatContextValue>;
    textSelectionContextValues?: Partial<SelectionContextValue>;
    audioSettingsContextValues?: Partial<AudioSettingsContextValue>;
    projectContextValues?: Partial<ProjectContextValue>;
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
export const StoryProvider: React.FC<StoryProviderProps> = ({
    children,
    authContextValues = {},
    chatContextValues = {},
    textSelectionContextValues = {},
    audioSettingsContextValues = {},
    projectContextValues = {},
    taskContextValues = {},
    configContextValues = {},
}) => {
    return (
        <ThemeProvider>
            <MockConfigProvider mockValues={configContextValues}>
                <MockAuthProvider mockValues={authContextValues}>
                    <MockAudioSettingsProvider mockValues={audioSettingsContextValues}>
                        <MockProjectProvider mockValues={projectContextValues}>
                            <MockTextSelectionProvider mockValues={textSelectionContextValues}>
                                <MockTaskProvider mockValues={taskContextValues}>
                                    <MockChatProvider mockValues={chatContextValues}>{children}</MockChatProvider>
                                </MockTaskProvider>
                            </MockTextSelectionProvider>
                        </MockProjectProvider>
                    </MockAudioSettingsProvider>
                </MockAuthProvider>
            </MockConfigProvider>
        </ThemeProvider>
    );
};
