export interface SelectionState {
    selectedText: string | null;
    selectionRange: Range | null;
    menuPosition: { x: number; y: number } | null;
    sourceMessageId: string | null;
    isMenuOpen: boolean;
}

export interface SelectionContextValue extends SelectionState {
    setSelection: (text: string, range: Range, messageId: string, position: { x: number; y: number }) => void;
    clearSelection: () => void;
    handleFollowUpQuestion: () => void;
}

export interface SelectableMessageContentProps {
    messageId: string;
    children: React.ReactNode;
    isAIMessage: boolean;
}

export interface SelectionContextMenuProps {
    isOpen: boolean;
    position: { x: number; y: number } | null;
    selectedText: string;
    onClose: () => void;
}