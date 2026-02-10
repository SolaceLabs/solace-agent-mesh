import { useAuthContext } from "./useAuthContext";
import { useConfigContext } from "./useConfigContext";

export function useIsProjectOwner(projectUserId: string) {
    const { userInfo } = useAuthContext();
    const { configUseAuthorization } = useConfigContext();

    // If authorization is disabled, consider the user as the owner
    if (!configUseAuthorization) {
        return true;
    }
    const currentUsername = userInfo?.username as string | undefined;

    if (!currentUsername) {
        return false;
    }

    return currentUsername.toLowerCase() === projectUserId.toLowerCase();
}
