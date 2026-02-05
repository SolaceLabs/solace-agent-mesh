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
        isMenuOpen: false,
    });

    const setSelection = useCallback((text: string, range: Range, messageId: string, position: { x: number; y: number }) => {
        setState({
            selectedText: text,
            selectionRange: range,
            menuPosition: position,
            sourceMessageId: messageId,
            isMenuOpen: true,
        });
    }, []);

    const clearSelection = useCallback(() => {
        setState({
            selectedText: null,
            selectionRange: null,
            menuPosition: null,
            sourceMessageId: null,
            isMenuOpen: false,
        });
    }, []);

    const handleFollowUpQuestion = useCallback(() => {
        if (state.selectedText) {
            // Dispatch custom event for ChatInputArea to handle
            window.dispatchEvent(
                new CustomEvent("follow-up-question", {
                    detail: { text: state.selectedText },
                })
            );
            clearSelection();
        }
    }, [state.selectedText, clearSelection]);

    const value: SelectionContextValue = {
        ...state,
        setSelection,
        clearSelection,
        handleFollowUpQuestion,
    };

    return <TextSelectionContext.Provider value={value}>{children}</TextSelectionContext.Provider>;
};
