import { useState, useEffect, type ReactNode } from "react";
import { authenticatedFetch } from "../utils/api";
import { ConfigContext, type ConfigContextValue } from "../contexts";
import { useCsrfContext } from "../hooks/useCsrfContext";

interface BackendConfig {
    frontend_server_url: string;
    frontend_auth_login_url: string;
    frontend_use_authorization: boolean;
    frontend_welcome_message: string;
    frontend_redirect_url: string;
    frontend_collect_feedback: boolean;
    frontend_bot_name: string;
    frontend_feature_enablement?: Record<string, boolean>;
    persistence_enabled?: boolean;
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
                let configResponse = await authenticatedFetch("/api/v1/config", {
                    credentials: "include",
                    headers: { Accept: "application/json" },
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
                        configResponse = await authenticatedFetch("/api/v1/config", {
                            credentials: "include",
                            headers: {
                                "X-CSRF-TOKEN": csrfToken,
                                Accept: "application/json",
                            },
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

                // Map backend fields to ConfigContextValue fields
                const mappedConfig: ConfigContextValue = {
                    configServerUrl: data.frontend_server_url,
                    configAuthLoginUrl: data.frontend_auth_login_url,
                    configUseAuthorization: effectiveUseAuthorization,
                    configWelcomeMessage: data.frontend_welcome_message,
                    configRedirectUrl: data.frontend_redirect_url,
                    configCollectFeedback: data.frontend_collect_feedback,
                    configBotName: data.frontend_bot_name,
                    configFeatureEnablement: data.frontend_feature_enablement ?? {},
                    frontend_use_authorization: data.frontend_use_authorization,
                    persistenceEnabled: data.persistence_enabled ?? true,
                };
                if (isMounted) {
                    RETAINED_CONFIG = mappedConfig;
                    setConfig(mappedConfig);
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
        return (
            <div className="flex min-h-screen items-center justify-center bg-white dark:bg-gray-900">
                <div className="text-center">
                    <div className="border-solace-green mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-b-2"></div>
                    <h1 className="text-2xl text-black dark:text-white">Loading Configuration...</h1>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-red-100 dark:bg-red-900">
                <div className="rounded border border-red-400 bg-white p-4 text-center dark:bg-gray-800">
                    <h1 className="text-xl font-bold text-red-700 dark:text-red-300">Configuration Error</h1>
                    <p className="mt-2 text-red-600 dark:text-red-200">{error}</p>
                    <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">Please check the backend server and network connection, then refresh the page.</p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex min-h-screen items-center justify-center bg-white dark:bg-gray-900">
            <div className="text-center">
                <div className="border-solace-green mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-b-2"></div>
                <h1 className="text-2xl">Initializing Application...</h1>
            </div>
        </div>
    );
}
