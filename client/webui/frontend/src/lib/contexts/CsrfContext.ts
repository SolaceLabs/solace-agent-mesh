import { createContext } from "react";

export interface CsrfContextValue {
    fetchCsrfToken: () => Promise<string | null>;
    clearCsrfToken: () => void;
}

export const CsrfContext = createContext<CsrfContextValue | null>(null);
