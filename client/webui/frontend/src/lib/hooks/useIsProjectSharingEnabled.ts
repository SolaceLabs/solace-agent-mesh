import { useBooleanFlagValue } from "@openfeature/react-sdk";

/**
 * Hook to check if project sharing is enabled.
 * Project sharing is an enterprise feature and is not available in the community edition.
 */
export function useIsProjectSharingEnabled(): boolean {
    return useBooleanFlagValue("project_sharing", false);
}
