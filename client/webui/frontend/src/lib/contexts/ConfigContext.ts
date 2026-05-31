import { createContext } from "react";

export interface ValidationLimits {
    projectNameMax?: number;
    projectDescriptionMax?: number;
    projectInstructionsMax?: number;
    projectFileDescriptionMax?: number;
    maxPerFileUploadSizeBytes?: number;
    maxBatchUploadSizeBytes?: number;
    maxZipUploadSizeBytes?: number;
    maxProjectSizeBytes?: number;
}

export interface ConfigContextValue {
    webuiServerUrl: string;
    platformServerUrl: string;
    configAuthLoginUrl: string;
    configUseAuthorization: boolean;
    configWelcomeMessage: string;
    /**
     * Agent Mode: chat-only, single-agent layout selected per Teams tab via the
     * `agentMode=true` URL parameter, placed in the hash query after the route
     * (`/#/chat?agentMode=true&agent=Foo`). URL-derived (synchronous read of the
     * hash query via getHashQueryParams), not a server-sent flag — deliberately
     * kept out of configFeatureEnablement and never persisted to localStorage so
     * an admin on the same origin cannot inherit a sticky Agent Mode.
     */
    agentMode: boolean;
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
     * Whether Identity Service is configured.
     * When null, Identity Service is not configured.
     */
    identityServiceType: string | null;

    /**
     * Whether binary artifact preview is enabled.
     * When true, Office documents can be previewed in the browser via PDF conversion.
     * Requires LibreOffice to be installed on the server.
     */
    binaryArtifactPreviewEnabled?: boolean;
}

export const ConfigContext = createContext<ConfigContextValue | null>(null);
