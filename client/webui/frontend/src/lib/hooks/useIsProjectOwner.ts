import { useAuthContext } from "./useAuthContext";

export function useIsProjectOwner(projectUserId: string | undefined) {
    const { userInfo } = useAuthContext();
    const currentUsername = userInfo?.username as string | undefined;

    if (!currentUsername || !projectUserId) return false;
    return currentUsername === projectUserId;
}
