import React, { useCallback, useEffect, useRef } from "react";

import { useTextSelection } from "./useTextSelection";
import { getSelectedText, getSelectionRange, getSelectionBoundingRect, calculateMenuPosition, isValidSelection, isSelectionContainedInElement } from "./selectionUtils";
import type { SelectableMessageContentProps } from "./types";

export const SelectableMessageContent: React.FC<SelectableMessageContentProps> = ({ messageId, children, isAIMessage }) => {
    const { setSelection, clearSelection } = useTextSelection();
    const containerRef = useRef<HTMLDivElement>(null);

    const handleMouseUp = useCallback(() => {
        // Only process if this is an AI message
        if (!isAIMessage) {
            return;
        }

        // Small delay to ensure selection is complete
        setTimeout(() => {
            const text = getSelectedText();
            const range = getSelectionRange();
            const rect = getSelectionBoundingRect();

            // Validate selection
            if (!isValidSelection(text) || !range || !rect || !text) {
                return;
            }

            // Check if selection is within this message
            const container = containerRef.current;
            if (!container) {
                return;
            }

            // Verify the selection is fully contained within this message container
            // This prevents selections that span across multiple messages
            if (!isSelectionContainedInElement(range, container)) {
                return;
            }

            // Calculate menu position
            const position = calculateMenuPosition(rect);

            // Update selection state
            setSelection(text, range, messageId, position);
        }, 10);
    }, [isAIMessage, messageId, setSelection]);

    useEffect(() => {
        const container = containerRef.current;
        if (!container || !isAIMessage) {
            return;
        }

        document.addEventListener("mouseup", handleMouseUp);

        return () => {
            document.removeEventListener("mouseup", handleMouseUp);
        };
    }, [handleMouseUp, isAIMessage]);

    // Clear selection when component unmounts
    useEffect(() => {
        return () => {
            clearSelection();
        };
    }, [clearSelection]);

    return (
        <div ref={containerRef} className="selectable-message-content">
            {children}
        </div>
    );
};
