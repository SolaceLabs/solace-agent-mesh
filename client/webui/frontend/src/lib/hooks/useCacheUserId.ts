import { useAuthContext } from "./useAuthContext";

/**
 * Returns a stable identifier for the current user, suitable for scoping
 * React Query cache keys so one user can never see another user's cached
 * results. Falls back to "anonymous" when authorization is disabled or the
 * user has not yet been resolved (single-user / pre-auth case).
 */
export function useCacheUserId(): string {
    const { userInfo } = useAuthContext();
    const username = userInfo?.username;
    if (typeof username === "string" && username.length > 0) return username;
    const id = userInfo?.id;
    if (typeof id === "string" && id.length > 0) return id;
    return "anonymous";
}
