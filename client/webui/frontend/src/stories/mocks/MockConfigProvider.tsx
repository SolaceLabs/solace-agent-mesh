import { ConfigContext, type ConfigContextValue } from "@/lib/contexts/ConfigContext";
import { api } from "@/lib/api";
import React, { useEffect } from "react";

// Default mock values for ConfigContext
const defaultMockConfigContext: ConfigContextValue = {
    chatServerUrl: "http://localhost:8000",
    platformServerUrl: "http://localhost:8001",
    configAuthLoginUrl: "http://localhost:8000/auth/login",
    configUseAuthorization: false,
    configWelcomeMessage: "Welcome to the mock Solace Agent Mesh!",
    configRedirectUrl: "http://localhost:3000",
    configCollectFeedback: false,
    configBotName: "Mock Bot",
    configLogoUrl: "",
    frontend_use_authorization: false,
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
    const contextValue = {
        ...defaultMockConfigContext,
        ...mockValues,
    };

    useEffect(() => {
        api.configure(contextValue.chatServerUrl, contextValue.platformServerUrl);
    }, [contextValue.chatServerUrl, contextValue.platformServerUrl]);

    return <ConfigContext.Provider value={contextValue}>{children}</ConfigContext.Provider>;
};
