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
        // Clean up any stale logout flags from previous sessions
        sessionStorage.removeItem("logout_in_progress");
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
            if (event.key === "access_token" || event.key === "sam_access_token") {
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
                // Set flag to prevent automatic token refresh during logout
                sessionStorage.setItem("logout_in_progress", "true");

                // Call logout while we have an access token
                await api.webui.post("/api/v1/auth/logout");
            }
        } catch (error) {
            console.warn("Error during logout:", error);
        } finally {
            // Clear tokens from localStorage
            localStorage.removeItem("access_token");
            localStorage.removeItem("sam_access_token");
            localStorage.removeItem("refresh_token");

            // Clear local state
            setIsAuthenticated(false);
            setUserInfo(null);
            clearCsrfToken();

            // Clean up logout flag
            sessionStorage.removeItem("logout_in_progress");

            // Redirect to home page
            window.location.href = "/";
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
