import { useState, useCallback, useEffect } from "react";

import { api } from "@/lib/api";
import { useChatContext } from "@/lib/hooks/useChatContext";
import type { Session } from "@/lib/types";

export interface UseMoveSessionReturn {
    isMoveDialogOpen: boolean;
    sessionToMove: Session | null;
    handleMoveConfirm: (targetProjectId: string | null) => Promise<void>;
    closeMoveDialog: () => void;
}

/**
 * Hook that encapsulates the "Move to Project" session dialog logic.
 *
 * It listens for the `"open-move-session-dialog"` custom event dispatched by
 * `RecentChatsPage` (and `SessionList`) when the user clicks "Move to Project",
 * manages the dialog open/close state, and handles the API call to move the
 * session to a different project.
 */
export function useMoveSession(): UseMoveSessionReturn {
    const { addNotification } = useChatContext();
    const [isMoveDialogOpen, setIsMoveDialogOpen] = useState(false);
    const [sessionToMove, setSessionToMove] = useState<Session | null>(null);

    const handleOpenMoveDialog = useCallback((event: CustomEvent<{ session: Session }>) => {
        setSessionToMove(event.detail.session);
        setIsMoveDialogOpen(true);
    }, []);

    useEffect(() => {
        window.addEventListener("open-move-session-dialog", handleOpenMoveDialog as EventListener);
        return () => {
            window.removeEventListener("open-move-session-dialog", handleOpenMoveDialog as EventListener);
        };
    }, [handleOpenMoveDialog]);

    const handleMoveConfirm = useCallback(
        async (targetProjectId: string | null) => {
            if (!sessionToMove) return;

            try {
                await api.webui.patch(`/api/v1/sessions/${sessionToMove.id}/project`, { projectId: targetProjectId });

                window.dispatchEvent(
                    new CustomEvent("session-updated", {
                        detail: {
                            sessionId: sessionToMove.id,
                            projectId: targetProjectId,
                        },
                    })
                );

                addNotification?.("Session moved successfully", "success");
            } catch (error) {
                console.error("Failed to move session:", error);
                addNotification?.("Failed to move session", "warning");
            }
        },
        [sessionToMove, addNotification]
    );

    const closeMoveDialog = useCallback(() => {
        setIsMoveDialogOpen(false);
        setSessionToMove(null);
    }, []);

    return {
        isMoveDialogOpen,
        sessionToMove,
        handleMoveConfirm,
        closeMoveDialog,
    };
}
