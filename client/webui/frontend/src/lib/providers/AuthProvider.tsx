import React, { useState, useEffect, type ReactNode } from "react";

import { authenticatedFetch } from "@/lib/utils/api";
import { AuthContext } from "@/lib/contexts/AuthContext";
import { useConfigContext, useCsrfContext } from "@/lib/hooks";

interface AuthProviderProps {
    children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
    const { frontend_use_authorization: useAuthorization, configAuthLoginUrl: authLoginUrl } = useConfigContext();
    const { fetchCsrfToken, clearCsrfToken } = useCsrfContext();
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [userInfo, setUserInfo] = useState<Record<string, unknown> | null>(null);

    useEffect(() => {
        let isMounted = true;

        const checkAuthStatus = async () => {
            if (!useAuthorization) {
                if (isMounted) {
                    setIsAuthenticated(true);
                    setIsLoading(false);
                }
                return;
            }

            try {
                const userResponse = await authenticatedFetch("/api/v1/users/me", {
                    credentials: "include",
                    headers: { Accept: "application/json" },
                });

                if (userResponse.ok) {
                    const userData = await userResponse.json();
                    console.log("User is authenticated:", userData);

                    if (isMounted) {
                        setUserInfo(userData);
                        setIsAuthenticated(true);
                    }

                    // Get CSRF token for authenticated requests if not already cached
                    console.log("Fetching CSRF token for authenticated requests...");
                    await fetchCsrfToken();
                } else if (userResponse.status === 401) {
                    console.log("User is not authenticated");
                    if (isMounted) {
                        setIsAuthenticated(false);
                    }
                } else {
                    console.error("Unexpected response from /users/me:", userResponse.status);
                    if (isMounted) {
                        setIsAuthenticated(false);
                    }
                }
            } catch (authError) {
                console.error("Error checking authentication:", authError);
                if (isMounted) {
                    setIsAuthenticated(false);
                }
            } finally {
                if (isMounted) {
                    setIsLoading(false);
                }
            }
        };

        checkAuthStatus();

        const handleStorageChange = (event: StorageEvent) => {
            if (event.key === "access_token") {
                checkAuthStatus();
            }
        };

        window.addEventListener("storage", handleStorageChange);

        return () => {
            isMounted = false;
            window.removeEventListener("storage", handleStorageChange);
        };
    }, [useAuthorization, authLoginUrl, fetchCsrfToken]);

    const login = () => {
        window.location.href = authLoginUrl;
    };

    const logout = () => {
        setIsAuthenticated(false);
        setUserInfo(null);
        clearCsrfToken();
    };

    if (isLoading) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-white dark:bg-gray-900">
                <div className="text-center">
                    <div className="border-solace-green mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-b-2"></div>
                    <h1 className="text-2xl text-black dark:text-white">Checking Authentication...</h1>
                </div>
            </div>
        );
    }

    return (
        <AuthContext.Provider
            value={{
                isAuthenticated,
                useAuthorization,
                login,
                logout,
                userInfo,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
};
