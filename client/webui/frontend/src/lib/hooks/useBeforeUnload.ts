import { useEffect, useCallback } from 'react';
import { useChatContext } from './useChatContext';

/**
 * Custom hook to handle beforeunload warning when chat data is present
 * Displays a browser confirmation dialog warning users about losing chat history
 * Remove this hook when session history is saved
 */
export function useBeforeUnload() {
    const { messages } = useChatContext();

    /**
     * Cross-browser beforeunload event handler
     * Handles different browser implementations and compatibility issues
     */
    const handleBeforeUnload = useCallback((event: BeforeUnloadEvent): string | void => {
        if (messages.length <= 1) {
            return;
        }

        event.preventDefault();

        // Some browsers use the return value as the dialog message
        return "Are you sure you want to leave? Your chat history will be lost.";
    }, [messages.length]);

    /**
     * Setup and cleanup beforeunload event listener
     */
    useEffect(() => {
        window.addEventListener('beforeunload', handleBeforeUnload);

        return () => {
            window.removeEventListener('beforeunload', handleBeforeUnload);
        };
    },  [handleBeforeUnload]);
}
