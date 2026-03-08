import { useEffect, useCallback } from "react";
import { useChatContext } from "./useChatContext";
import { useConfigContext } from "./useConfigContext";

export function useBeforeUnload() {
    const { messages, isResponding } = useChatContext();
    const config = useConfigContext();

    /**
     * Cross-browser beforeunload event handler
     * Warns when:
     * 1. Persistence is disabled and messages exist (chat history would be lost)
     * 2. A task is running and background tasks are disabled (task results would be lost)
     */
    const handleBeforeUnload = useCallback(
        (event: BeforeUnloadEvent): string | void => {
            // Case 1: Task is running and background tasks are disabled
            // In this case, navigating away may cause the user to lose the task results
            if (isResponding && config?.backgroundTasksEnabled === false) {
                event.preventDefault();
                return "A task is currently running. If you leave now, you may lose the response. Are you sure you want to leave?";
            }

            // Case 2: Persistence disabled and messages exist (original behavior)
            if (config?.persistenceEnabled !== false) {
                return;
            }

            if (messages.length <= 1) {
                return;
            }

            event.preventDefault();

            return "Are you sure you want to leave? Your chat history will be lost.";
        },
        [messages.length, config?.persistenceEnabled, config?.backgroundTasksEnabled, isResponding]
    );

    /**
     * Setup and cleanup beforeunload event listener
     */
    useEffect(() => {
        window.addEventListener("beforeunload", handleBeforeUnload);

        return () => {
            window.removeEventListener("beforeunload", handleBeforeUnload);
        };
    }, [handleBeforeUnload]);
}
