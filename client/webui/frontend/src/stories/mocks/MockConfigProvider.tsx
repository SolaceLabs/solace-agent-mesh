import { ConfigContext, type ConfigContextValue } from "@/lib/contexts/ConfigContext";
import { api } from "@/lib/api";
import React, { useMemo, useRef } from "react";
import { OpenFeature, OpenFeatureProvider } from "@openfeature/react-sdk";
import { SamFeatureProvider } from "@/lib/providers/openfeature";

// Default mock values for ConfigContext
const defaultMockConfigContext: ConfigContextValue = {
    webuiServerUrl: "", // Empty for relative URLs (same-origin)
    platformServerUrl: "http://localhost:8001",
    configAuthLoginUrl: "http://localhost:8000/auth/login",
    configUseAuthorization: false,
    configWelcomeMessage: "Welcome to the mock Solace Agent Mesh!",
    configRedirectUrl: "http://localhost:3000",
    configCollectFeedback: false,
    configBotName: "Mock Bot",
    configLogoUrl: "",
    frontend_use_authorization: false,
    platformConfigured: true,
    identityServiceType: null,
};

interface MockConfigProviderProps {
    children: React.ReactNode;
    mockValues?: Partial<ConfigContextValue>;
}

/**
 * A mock provider for ConfigContext to be used in Storybook stories.
 *
 * @param props.children - The child components to render within the provider
 * @param props.mockValues - Optional partial ConfigContextValue to override default values
 */
export const MockConfigProvider: React.FC<MockConfigProviderProps> = ({ children, mockValues = {} }) => {
    const contextValue = useMemo(
        () => ({
            ...defaultMockConfigContext,
            ...mockValues,
        }),
        [mockValues]
    );

    const featureFlags = contextValue.configFeatureEnablement;
    const prevFlagsRef = useRef<Record<string, boolean> | undefined>(undefined);
    if (featureFlags !== undefined && featureFlags !== prevFlagsRef.current) {
        OpenFeature.setProvider(new SamFeatureProvider(featureFlags));
        prevFlagsRef.current = featureFlags;
    }

    api.configure(contextValue.webuiServerUrl, contextValue.platformServerUrl);

    return (
        <ConfigContext.Provider value={contextValue}>
            <OpenFeatureProvider>{children}</OpenFeatureProvider>
        </ConfigContext.Provider>
    );
};
