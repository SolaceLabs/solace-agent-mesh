import { render, type RenderOptions, type RenderResult } from "@testing-library/react";
import { OpenFeature, OpenFeatureProvider } from "@openfeature/react-sdk";
import { InMemoryProvider, type FlagValue } from "@openfeature/web-sdk";
import { MemoryRouter } from "react-router-dom";
import type { ReactElement } from "react";

import { StoryProvider } from "@/stories/mocks/StoryProvider";
import type { AuthContextValue, ChatContextValue, ConfigContextValue, ProjectContextValue, TaskContextValue } from "@/lib";

type FeatureFlagMap = Record<string, FlagValue>;

interface RenderWithProvidersOptions extends Omit<RenderOptions, "wrapper"> {
    featureFlags?: FeatureFlagMap;
    chatContextValues?: Partial<ChatContextValue>;
    authContextValues?: Partial<AuthContextValue>;
    configContextValues?: Partial<ConfigContextValue>;
    projectContextValues?: Partial<ProjectContextValue>;
    taskContextValues?: Partial<TaskContextValue>;
    initialPath?: string;
}

const VARIANT_KEY = "default";

function buildInMemoryProvider(flags: FeatureFlagMap): InMemoryProvider {
    const flagConfig = Object.fromEntries(
        Object.entries(flags).map(([flagKey, value]) => [
            flagKey,
            {
                variants: { [VARIANT_KEY]: value },
                defaultVariant: VARIANT_KEY,
                disabled: false,
            },
        ])
    );
    return new InMemoryProvider(flagConfig);
}

/**
 * Async render helper for tests that depend on OpenFeature flag resolution.
 *
 * Pre-sets the OpenFeature provider via `setProviderAndWait` before rendering
 * so the provider is READY on first render — `useBooleanFlagDetails` resolves
 * synchronously in `useState`'s initializer, no timing hacks needed.
 */
export async function renderWithProviders(
    ui: ReactElement,
    { featureFlags = {}, chatContextValues, authContextValues, configContextValues, projectContextValues, taskContextValues, initialPath = "/", ...rtlOptions }: RenderWithProvidersOptions = {}
): Promise<RenderResult> {
    await OpenFeature.setProviderAndWait(buildInMemoryProvider(featureFlags));

    return render(
        <MemoryRouter initialEntries={[initialPath]}>
            <OpenFeatureProvider>
                <StoryProvider
                    chatContextValues={chatContextValues}
                    authContextValues={authContextValues}
                    configContextValues={configContextValues}
                    projectContextValues={projectContextValues}
                    taskContextValues={taskContextValues}
                    skipFeatureFlagProvider
                >
                    {ui}
                </StoryProvider>
            </OpenFeatureProvider>
        </MemoryRouter>,
        rtlOptions
    );
}
