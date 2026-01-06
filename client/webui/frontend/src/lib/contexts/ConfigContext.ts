import { createContext } from "react";

export interface ValidationLimits {
    projectNameMax?: number;
    projectDescriptionMax?: number;
    projectInstructionsMax?: number;
    maxUploadSizeBytes?: number;
    maxZipUploadSizeBytes?: number;
}

export interface ConfigContextValue {
    webuiServerUrl: string;
    platformServerUrl: string;
    configAuthLoginUrl: string;
    configUseAuthorization: boolean;
    configWelcomeMessage: string;
    configRedirectUrl: string;
    configCollectFeedback: boolean;
    configBotName: string;
    configLogoUrl: string;
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

    /**
     * Whether background task execution is enabled globally.
     * When true, all tasks can run in background mode, allowing users to
     * navigate away and return to see completed results.
     */
    backgroundTasksEnabled?: boolean;

    /**
     * Default timeout for background tasks in milliseconds.
     * Tasks running longer than this will be automatically cancelled.
     */
    backgroundTasksDefaultTimeoutMs?: number;

    /**
     * Whether the platform service is configured.
     * When false, platform-dependent features (agent builder, connectors, etc.) are unavailable.
     */
    platformConfigured: boolean;

    /**
     * Whether automatic title generation is enabled for new chat sessions.
     * When true, the first message exchange will trigger AI-powered title generation.
     * Requires persistence to be enabled.
     */
    autoTitleGenerationEnabled?: boolean;
}

export const ConfigContext = createContext<ConfigContextValue | null>(null);
