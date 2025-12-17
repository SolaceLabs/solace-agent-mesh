import React, { useState, useEffect, type ReactNode } from "react";

import { api } from "@/lib/api";
import { AuthContext } from "@/lib/contexts/AuthContext";
import { useConfigContext, useCsrfContext } from "@/lib/hooks";

interface AuthProviderProps {
    children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
    const { configUseAuthorization, configAuthLoginUrl } = useConfigContext();
    const { fetchCsrfToken, clearCsrfToken } = useCsrfContext();
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [userInfo, setUserInfo] = useState<Record<string, unknown> | null>(null);

    useEffect(() => {
        let isMounted = true;

        const checkAuthStatus = async () => {
            if (!configUseAuthorization) {
                if (isMounted) {
                    setIsAuthenticated(true);
                    setIsLoading(false);
                }
                return;
            }

            try {
                const userData = await api.webui.get<Record<string, unknown>>("/api/v1/users/me");
                console.log("User is authenticated:", userData);

                if (isMounted) {
                    setUserInfo(userData);
                    setIsAuthenticated(true);
                }

                console.log("Fetching CSRF token for authenticated requests...");
                await fetchCsrfToken();
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
    }, [configUseAuthorization, configAuthLoginUrl, fetchCsrfToken]);

    const login = () => {
        window.location.href = configAuthLoginUrl;
    };

    const logout = async () => {
        try {
            if (configUseAuthorization) {
                await api.webui.post("/api/v1/auth/logout");
            }
        } catch (error) {
            console.error("Error calling logout endpoint:", error);
        } finally {
            setIsAuthenticated(false);
            setUserInfo(null);
            clearCsrfToken();
        }
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
                useAuthorization: configUseAuthorization,
                login,
                logout,
                userInfo,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
};
