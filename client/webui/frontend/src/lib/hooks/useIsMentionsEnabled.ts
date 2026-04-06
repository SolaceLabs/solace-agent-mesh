import { useBooleanFlagValue } from "@openfeature/react-sdk";
import { useConfigContext } from "./useConfigContext";

/**
 * Hook to check if mentions (@user) feature is enabled.
 * Requires both the feature flag and an identity service to be configured.
 */
export function useIsMentionsEnabled(): boolean {
    const { identityServiceType } = useConfigContext();
    const flagEnabled = useBooleanFlagValue("mentions", false);
    return flagEnabled && identityServiceType !== null;
}
