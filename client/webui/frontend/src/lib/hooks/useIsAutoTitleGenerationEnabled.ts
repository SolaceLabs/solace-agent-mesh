import { useBooleanFlagValue } from "@openfeature/react-sdk";
import { useConfigContext } from "./useConfigContext";

/**
 * Hook to check if automatic title generation is enabled.
 * Requires both the feature flag and persistence to be active.
 */
export function useIsAutoTitleGenerationEnabled(): boolean {
    const { persistenceEnabled } = useConfigContext();
    const flagEnabled = useBooleanFlagValue("auto_title_generation", false);
    return flagEnabled && (persistenceEnabled ?? false);
}
