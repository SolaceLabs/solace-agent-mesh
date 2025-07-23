import { useContext } from "react";

import { CsrfContext } from "../contexts/CsrfContext";
import type { CsrfContextValue } from "../contexts/CsrfContext";

export function useCsrfContext(): CsrfContextValue {
    const context = useContext(CsrfContext);
    if (!context) {
        throw new Error("useCsrf must be used within a CsrfProvider");
    }
    return context;
}
