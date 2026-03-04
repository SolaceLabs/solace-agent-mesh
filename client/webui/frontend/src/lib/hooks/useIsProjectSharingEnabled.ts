import { useConfigContext } from "./useConfigContext";

/**
 * Hook to check if project sharing is enabled.
 * Project sharing is an enterprise feature and is not available in the community edition.
 */
export function useIsProjectSharingEnabled(): boolean {
    const { configFeatureEnablement } = useConfigContext();
    return configFeatureEnablement?.projectSharingEnabled ?? false;
}
