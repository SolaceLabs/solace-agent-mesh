export interface SelectionState {
    selectedText: string | null;
    selectionRange: Range | null;
    menuPosition: { x: number; y: number } | null;
    sourceMessageId: string | null;
    sourceTaskId: string | null;
    isMenuOpen: boolean;
}

export interface SelectionContextValue extends SelectionState {
    setSelection: (text: string, range: Range, messageId: string, taskId: string, position: { x: number; y: number }) => void;
    clearSelection: () => void;
    handleFollowUpQuestion: () => void;
}

export interface SelectableMessageContentProps {
    messageId: string;
    taskId?: string;
    children: React.ReactNode;
    isAIMessage: boolean;
}

export interface SelectionContextMenuProps {
    isOpen: boolean;
    position: { x: number; y: number } | null;
    selectedText: string;
    sourceTaskId: string | null;
    onClose: () => void;
}
