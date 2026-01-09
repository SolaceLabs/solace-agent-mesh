import React, { useState, useEffect, type ReactNode } from "react";

import { api } from "@/lib/api";
import { AuthContext } from "@/lib/contexts/AuthContext";
import { useConfigContext, useCsrfContext } from "@/lib/hooks";
import { EmptyState } from "../components";

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
                setIsAuthenticated(false);
                setUserInfo(null);
                clearCsrfToken();

                // Clear tokens from localStorage - set in authCallback.tsx
                localStorage.removeItem("access_token");
                localStorage.removeItem("refresh_token");
            }
        } catch (error) {
            console.error("Error calling logout endpoint:", error);
        }
    };

    if (isLoading) {
        return <EmptyState variant="loading" title="Checking Authentication..." className="h-screen w-screen" />;
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
