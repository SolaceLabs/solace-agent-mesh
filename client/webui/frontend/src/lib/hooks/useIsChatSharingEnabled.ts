import { useConfigContext } from "./useConfigContext";

/**
 * Hook to check if chat sharing is enabled.
 * Chat sharing allows users to create shareable links for chat sessions
 * and collaborate with other users on shared conversations.
 * Requires identity service and SQL persistence to be configured.
 */
export function useIsChatSharingEnabled(): boolean {
    const { configFeatureEnablement } = useConfigContext();
    return configFeatureEnablement?.chatSharing ?? false;
}
