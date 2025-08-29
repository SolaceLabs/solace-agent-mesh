import { createContext } from "react";

export interface ConfigContextValue {
    configServerUrl: string;
    configAuthLoginUrl: string;
    configUseAuthorization: boolean;
    configWelcomeMessage: string;
    configRedirectUrl: string;
    configCollectFeedback: boolean;
    configBotName: string;
    /**
     * Authorization flag from frontend config
     * @deprecated Consider using configUseAuthorization instead as this may be redundant
     */
    frontend_use_authorization: boolean;
    /**
     * Indicates if session persistence is enabled on the backend
     * When false, sessions are stored in-memory only (not persisted across restarts)
     */
    persistenceEnabled?: boolean;
}

export const ConfigContext = createContext<ConfigContextValue | null>(null);
