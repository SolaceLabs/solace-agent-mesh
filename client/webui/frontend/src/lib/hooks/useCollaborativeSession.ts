import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import { useAuthContext } from "@/lib/hooks/useAuthContext";

interface Session {
    userId?: string;
    ownerDisplayName?: string | null;
    ownerEmail?: string | null;
}

interface CollaborativeSessionState {
    isCollaborativeSession: boolean;
    hasSharedEditors: boolean;
    currentUserEmail: string;
    sessionOwnerName: string | null;
    sessionOwnerEmail: string | null;
}

interface UseCollaborativeSessionReturn extends CollaborativeSessionState {
    /** Detect whether the given session is collaborative and update state accordingly */
    detectCollaborativeSession: (session: Session | null, sessionId: string) => Promise<void>;
    /** Reset collaborative state (e.g., when starting a new session) */
    resetCollaborativeState: () => void;
    /** Get the current user ID (from AuthContext or /auth/me fallback) */
    getCurrentUserId: () => string | null;
}

/**
 * Manages collaborative session detection and state.
 *
 * Uses /api/v1/auth/me (not /api/v1/users/me) because it returns the user's
 * email and display name, which /api/v1/users/me does not include. This is
 * needed for collaborative session UI (showing who owns the session).
 * The /auth/me endpoint also works in dev mode when OAuth is disabled.
 */
export function useCollaborativeSession(sessionId: string): UseCollaborativeSessionReturn {
    const { userInfo } = useAuthContext();
    const [isCollaborativeSession, setIsCollaborativeSession] = useState(false);
    const [hasSharedEditors, setHasSharedEditors] = useState(false);
    const [currentUserEmail, setCurrentUserEmail] = useState("");
    const [sessionOwnerName, setSessionOwnerName] = useState<string | null>(null);
    const [sessionOwnerEmail, setSessionOwnerEmail] = useState<string | null>(null);
    const currentUserIdFromAuth = useRef("");

    // Fetch current user info on mount for email (not available from /users/me)
    useEffect(() => {
        api.webui
            .get("/api/v1/auth/me")
            .then((data: { id?: string; email?: string }) => {
                if (data?.email) setCurrentUserEmail(data.email);
                if (data?.id) currentUserIdFromAuth.current = data.id;
            })
            .catch(() => {
                // Silently fail — currentUserEmail will remain empty
            });
    }, []);

    const getCurrentUserId = useCallback((): string | null => {
        return typeof userInfo?.username === "string" ? userInfo.username : currentUserIdFromAuth.current || null;
    }, [userInfo]);

    const resetCollaborativeState = useCallback(() => {
        setIsCollaborativeSession(false);
        setHasSharedEditors(false);
        setSessionOwnerName(null);
        setSessionOwnerEmail(null);
    }, []);

    const detectCollaborativeSession = useCallback(
        async (session: Session | null, newSessionId: string) => {
            setHasSharedEditors(false);

            const currentUserId = getCurrentUserId();
            const sessionOwnerId = session?.userId;

            if (currentUserId && sessionOwnerId && currentUserId !== sessionOwnerId) {
                setIsCollaborativeSession(true);
                setSessionOwnerName(session?.ownerDisplayName || sessionOwnerId);
                setSessionOwnerEmail(session?.ownerEmail || sessionOwnerId);
            } else {
                setIsCollaborativeSession(false);
                setSessionOwnerName(null);
                setSessionOwnerEmail(null);

                // Check if the owner has shared with editors (for showing collaborative UI elements)
                try {
                    const { getShareLinkForSession, getShareUsers } = await import("@/lib/api/share");
                    const link = await getShareLinkForSession(newSessionId);
                    if (link) {
                        const usersResponse = await getShareUsers(link.shareId);
                        const hasEditors = (usersResponse.users || []).some(u => u.accessLevel === "RESOURCE_EDITOR");
                        setHasSharedEditors(hasEditors);
                    }
                } catch {
                    setHasSharedEditors(false);
                }
            }
        },
        [getCurrentUserId]
    );

    // Listen for share-updated events to refresh hasSharedEditors flag
    useEffect(() => {
        const handleShareUpdated = async (event: Event) => {
            const detail = (event as CustomEvent).detail;
            if (detail?.sessionId === sessionId && !isCollaborativeSession) {
                try {
                    const { getShareLinkForSession, getShareUsers } = await import("@/lib/api/share");
                    const link = await getShareLinkForSession(sessionId);
                    if (link) {
                        const usersResponse = await getShareUsers(link.shareId);
                        const hasEditors = (usersResponse.users || []).some(u => u.accessLevel === "RESOURCE_EDITOR");
                        setHasSharedEditors(hasEditors);
                    } else {
                        setHasSharedEditors(false);
                    }
                } catch {
                    // Silently fail
                }
            }
        };
        window.addEventListener("share-updated", handleShareUpdated);
        return () => window.removeEventListener("share-updated", handleShareUpdated);
    }, [sessionId, isCollaborativeSession]);

    return {
        isCollaborativeSession,
        hasSharedEditors,
        currentUserEmail,
        sessionOwnerName,
        sessionOwnerEmail,
        detectCollaborativeSession,
        resetCollaborativeState,
        getCurrentUserId,
    };
}
