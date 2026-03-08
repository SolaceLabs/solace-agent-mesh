import React, { useState, useCallback, type ReactNode } from "react";

import type { SelectionState, SelectionContextValue } from "./types";
import { TextSelectionContext } from "./TextSelectionContext";

interface TextSelectionProviderProps {
    children: ReactNode;
}

export const TextSelectionProvider: React.FC<TextSelectionProviderProps> = ({ children }) => {
    const [state, setState] = useState<SelectionState>({
        selectedText: null,
        selectionRange: null,
        menuPosition: null,
        sourceMessageId: null,
        sourceTaskId: null,
        isMenuOpen: false,
    });

    const setSelection = useCallback((text: string, range: Range, messageId: string, taskId: string, position: { x: number; y: number }) => {
        setState({
            selectedText: text,
            selectionRange: range,
            menuPosition: position,
            sourceMessageId: messageId,
            sourceTaskId: taskId,
            isMenuOpen: true,
        });
    }, []);

    const clearSelection = useCallback(() => {
        setState({
            selectedText: null,
            selectionRange: null,
            menuPosition: null,
            sourceMessageId: null,
            sourceTaskId: null,
            isMenuOpen: false,
        });
    }, []);

    const handleFollowUpQuestion = useCallback(() => {
        if (state.selectedText) {
            // Dispatch custom event for ChatInputArea to handle
            // Include sourceTaskId so we can link back to the original message for scroll-to-source
            window.dispatchEvent(
                new CustomEvent("follow-up-question", {
                    detail: { text: state.selectedText, sourceMessageId: state.sourceTaskId },
                })
            );
            clearSelection();
        }
    }, [state.selectedText, state.sourceTaskId, clearSelection]);

    const value: SelectionContextValue = {
        ...state,
        setSelection,
        clearSelection,
        handleFollowUpQuestion,
    };

    return <TextSelectionContext.Provider value={value}>{children}</TextSelectionContext.Provider>;
};
