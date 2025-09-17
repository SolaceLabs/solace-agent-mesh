import { createContext } from "react";

export interface ConfigContextValue {
    configServerUrl: string;
    configAuthLoginUrl: string;
    configUseAuthorization: boolean;
    configWelcomeMessage: string;
    configRedirectUrl: string;
    configCollectFeedback: boolean;
    configBotName: string;
    configFeatureEnablement?: Record<string, boolean>;
    /**
     * Authorization flag from frontend config
     * @deprecated Consider using configUseAuthorization instead as this may be redundant
     */
    frontend_use_authorization: boolean;

    persistenceEnabled?: boolean;
}

export const ConfigContext = createContext<ConfigContextValue | null>(null);
