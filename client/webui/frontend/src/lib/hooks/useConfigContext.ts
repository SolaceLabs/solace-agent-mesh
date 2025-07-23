import { useContext } from "react";

import { ConfigContext } from "@/lib/contexts";
import type { ConfigContextValue } from "@/lib/contexts";

export function useConfigContext(): ConfigContextValue {
    const context = useContext(ConfigContext);
    if (context === null) {
        throw new Error("useConfig must be used within a ConfigProvider");
    }
    return context;
}
