import { useAuthContext } from "./useAuthContext";
import { useConfigContext } from "./useConfigContext";
import { useIsProjectSharingEnabled } from "./useIsProjectSharingEnabled";

export function useIsProjectOwner(projectUserId: string) {
    const { userInfo } = useAuthContext();
    const { configUseAuthorization } = useConfigContext();
    const isProjectSharingEnabled = useIsProjectSharingEnabled();

    // If authorization is disabled, consider the user as the owner
    // If project sharing is not enabled, ownership is not relevant, consider the user as the owner
    if (!configUseAuthorization || !isProjectSharingEnabled) {
        return true;
    }
    const currentUsername = userInfo?.username as string | undefined;

    if (!currentUsername) {
        return false;
    }

    return currentUsername.toLowerCase() === projectUserId.toLowerCase();
}
