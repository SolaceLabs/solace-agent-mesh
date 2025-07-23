import { useContext } from "react";

import { ThemeContext } from "../contexts";
import type { ThemeContextValue } from "../contexts";

export function useThemeContext(): ThemeContextValue {
    const context = useContext(ThemeContext);
    if (context === null) {
        throw new Error("useThemeContext must be used within a ThemeProvider");
    }
    return context;
}
