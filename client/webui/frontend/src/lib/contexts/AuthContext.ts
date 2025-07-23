import { createContext } from "react";

export interface AuthContextValue {
    isAuthenticated: boolean;
    useAuthorization: boolean;
    login: () => void;
    logout: () => void;
    userInfo: Record<string, unknown> | null;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
