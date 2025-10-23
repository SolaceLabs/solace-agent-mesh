import { AuthContext, type AuthContextValue } from "@/lib/contexts/AuthContext";
import React from "react";

// Default mock values for AuthContext
const defaultMockAuthContext: AuthContextValue = {
    // State
    isAuthenticated: true,
    useAuthorization: false,
    userInfo: null,

    // Actions
    login: () => Promise.resolve(),
    logout: () => Promise.resolve(),
};

interface MockAuthProviderProps {
    children: React.ReactNode;
    mockValues?: Partial<AuthContextValue>;
}

export const MockAuthProvider: React.FC<MockAuthProviderProps> = ({ children, mockValues = {} }) => {
    // Create the context value with the mock values
    const contextValue: AuthContextValue = {
        ...defaultMockAuthContext,
        ...mockValues,
    };

    return <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>;
};
