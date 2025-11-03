import { createContext } from "react";

export interface ValidationLimits {
    projectNameMax?: number;
    projectDescriptionMax?: number;
    projectInstructionsMax?: number;
}

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
    
    /**
     * Whether projects feature is enabled.
     * Computed from feature flags and persistence status.
     */
    projectsEnabled?: boolean;
    
    /**
     * Validation limits from backend.
     * These are dynamically fetched from the backend to ensure
     * frontend and backend validation stay in sync.
     */
    validationLimits?: ValidationLimits;
}

export const ConfigContext = createContext<ConfigContextValue | null>(null);
