import { useEffect, useCallback } from "react";
import { useChatContext } from "./useChatContext";
import { useConfigContext } from "./useConfigContext";

/**
 * Custom hook to handle beforeunload warning when chat data is present
 * Only displays warning when persistence is disabled (in-memory mode)
 * When persistence is enabled, sessions are saved so no warning is needed
 */
export function useBeforeUnload() {
    const { messages } = useChatContext();
    const config = useConfigContext();

    /**
     * Cross-browser beforeunload event handler
     * Only warns when persistence is disabled and messages exist
     */
    const handleBeforeUnload = useCallback(
        (event: BeforeUnloadEvent): string | void => {
            // Only show warning if persistence is disabled (in-memory mode)
            if (config?.persistenceEnabled !== false) {
                return;
            }

            if (messages.length <= 1) {
                return;
            }

            event.preventDefault();

            // Some browsers use the return value as the dialog message
            return "Are you sure you want to leave? Your chat history will be lost.";
        },
        [messages.length, config?.persistenceEnabled]
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
