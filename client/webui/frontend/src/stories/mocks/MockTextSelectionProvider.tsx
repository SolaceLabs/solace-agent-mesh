import { type SelectionContextValue } from "@/lib";
import { TextSelectionContext } from "@/lib/components/chat/selection/TextSelectionProvider";

interface MockTextSelectionProviderProps {
    children: React.ReactNode;
    mockValues: Partial<SelectionContextValue>;
}

const defaultTextSelectionValues: SelectionContextValue = {
    selectedText: null,
    selectionRange: null,
    menuPosition: null,
    sourceMessageId: null,
    isMenuOpen: false,
    setSelection: () => {},
    clearSelection: () => {},
    handleFollowUpQuestion: () => {},
};

export const MockTextSelectionProvider: React.FC<MockTextSelectionProviderProps> = ({ children, mockValues = {} }) => {
    const contextValue = {
        ...defaultTextSelectionValues,
        ...mockValues,
    };

    return <TextSelectionContext.Provider value={contextValue}>{children}</TextSelectionContext.Provider>;
};
