import { useState, useEffect, type ReactNode } from "react";
import { ConfigContext, type ConfigContextValue } from "../contexts";
import { useCsrfContext } from "../hooks/useCsrfContext";
import { EmptyState } from "../components";
import { api } from "../api";

interface BackendConfig {
    frontend_server_url: string;
    frontend_platform_server_url: string;
    frontend_auth_login_url: string;
    frontend_use_authorization: boolean;
    frontend_welcome_message: string;
    frontend_redirect_url: string;
    frontend_collect_feedback: boolean;
    frontend_bot_name: string;
    frontend_logo_url: string;
    frontend_feature_enablement?: Record<string, boolean>;
    persistence_enabled?: boolean;
    validation_limits?: {
        projectNameMax?: number;
        projectDescriptionMax?: number;
        projectInstructionsMax?: number;
    };
    background_tasks_config?: {
        default_timeout_ms?: number;
    };
}

interface ConfigProviderProps {
    children: ReactNode;
}

let RETAINED_CONFIG: ConfigContextValue | null = null;
let RETAINED_ERROR: string | null = null;

export function ConfigProvider({ children }: Readonly<ConfigProviderProps>) {
    const { fetchCsrfToken } = useCsrfContext();

    // Initialize state from retained values if available
    const [config, setConfig] = useState<ConfigContextValue | null>(RETAINED_CONFIG);
    const [loading, setLoading] = useState<boolean>(!RETAINED_CONFIG && !RETAINED_ERROR);
    const [error, setError] = useState<string | null>(RETAINED_ERROR);

    useEffect(() => {
        // If config or error was set from retained values, the effect has served its purpose for this "instance"
        if (RETAINED_CONFIG || RETAINED_ERROR) {
            return;
        }

        let isMounted = true;
        const initializeApp = async () => {
            setLoading(true);
            setError(null);

            try {
                let configResponse = await api.webui.get("/api/v1/config", {
                    credentials: "include",
                    headers: { Accept: "application/json" },
                    fullResponse: true,
                });

                let data: BackendConfig;

                if (!configResponse.ok) {
                    const errorText = await configResponse.text();
                    console.error("Initial config fetch failed:", configResponse.status, errorText);
                    if (configResponse.status === 403) {
                        console.log("Config fetch failed with 403, attempting to get CSRF token first...");
                        const csrfToken = await fetchCsrfToken();
                        if (!csrfToken) {
                            throw new Error("Failed to obtain CSRF token after config fetch failed.");
                        }
                        console.log("Retrying config fetch with CSRF token...");
                        configResponse = await api.webui.get("/api/v1/config", {
                            credentials: "include",
                            headers: {
                                "X-CSRF-TOKEN": csrfToken,
                                Accept: "application/json",
                            },
                            fullResponse: true,
                        });
                        if (!configResponse.ok) {
                            const errorTextRetry = await configResponse.text();
                            console.error("Config fetch retry failed:", configResponse.status, errorTextRetry);
                            throw new Error(`Failed to fetch config on retry: ${configResponse.status} ${errorTextRetry}`);
                        }
                        data = await configResponse.json();
                    } else {
                        throw new Error(`Failed to fetch config: ${configResponse.status} ${errorText}`);
                    }
                } else {
                    data = await configResponse.json();
                }

                const effectiveUseAuthorization = data.frontend_use_authorization ?? false;

                if (effectiveUseAuthorization) {
                    console.log("Fetching CSRF token for config-related requests...");
                    await fetchCsrfToken();
                }

                // Compute projectsEnabled from feature flags
                const projectsEnabled = data.frontend_feature_enablement?.projects ?? false;

                // Extract background tasks config from feature enablement
                const backgroundTasksEnabled = data.frontend_feature_enablement?.background_tasks ?? false;
                const backgroundTasksDefaultTimeoutMs = data.background_tasks_config?.default_timeout_ms ?? 3600000;

                // Check if platform service is configured
                const platformConfigured = Boolean(data.frontend_platform_server_url);

                // Extract auto title generation config from feature enablement
                const autoTitleGenerationEnabled = data.frontend_feature_enablement?.auto_title_generation ?? false;

                // Map backend fields to ConfigContextValue fields
                const mappedConfig: ConfigContextValue = {
                    webuiServerUrl: data.frontend_server_url,
                    platformServerUrl: data.frontend_platform_server_url,
                    configAuthLoginUrl: data.frontend_auth_login_url,
                    configUseAuthorization: effectiveUseAuthorization,
                    configWelcomeMessage: data.frontend_welcome_message,
                    configRedirectUrl: data.frontend_redirect_url,
                    configCollectFeedback: data.frontend_collect_feedback,
                    configBotName: data.frontend_bot_name,
                    configLogoUrl: data.frontend_logo_url,
                    configFeatureEnablement: data.frontend_feature_enablement ?? {},
                    frontend_use_authorization: data.frontend_use_authorization,
                    persistenceEnabled: data.persistence_enabled ?? false,
                    projectsEnabled,
                    validationLimits: data.validation_limits,
                    backgroundTasksEnabled,
                    backgroundTasksDefaultTimeoutMs,
                    platformConfigured,
                    autoTitleGenerationEnabled,
                };
                if (isMounted) {
                    RETAINED_CONFIG = mappedConfig;
                    setConfig(mappedConfig);

                    api.configure(mappedConfig.webuiServerUrl, mappedConfig.platformServerUrl);
                    console.log("API client configured with:", {
                        webui: mappedConfig.webuiServerUrl,
                        platform: mappedConfig.platformServerUrl,
                    });
                }
                console.log("App config processed and set:", mappedConfig);
            } catch (err: unknown) {
                console.error("Error initializing app:", err);
                if (isMounted) {
                    const errorMessage = (err as Error).message || "Failed to load application configuration.";
                    RETAINED_ERROR = errorMessage;
                    setError(errorMessage);
                }
            } finally {
                if (isMounted) {
                    setLoading(false);
                }
            }
        };

        initializeApp();

        return () => {
            isMounted = false;
        };
    }, [fetchCsrfToken]);

    if (config) {
        return <ConfigContext.Provider value={config}>{children}</ConfigContext.Provider>;
    }

    // If config is not yet available, handle loading and error states.
    if (loading) {
        return <EmptyState variant="loading" title="Loading Configuration..." className="h-screen w-screen" />;
    }

    if (error) {
        return <EmptyState variant="error" title="Configuration Error" subtitle="Please check the backend server and network connection, then refresh the page." className="h-screen w-screen" />;
    }

    return <EmptyState variant="loading" title="Initializing Application..." className="h-screen w-screen" />;
}
