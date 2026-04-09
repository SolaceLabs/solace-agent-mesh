import { useState, useEffect, useCallback } from "react";

interface UseListKeyboardNavigationOptions {
    /** Number of items in the list */
    itemCount: number;
    /** Whether the list is currently visible/active */
    isOpen: boolean;
    /** Called when user presses Enter/Tab on the active item */
    onSelect: (index: number) => void;
    /** Called when user presses Escape */
    onClose?: () => void;
    /** ID prefix for scrollIntoView (element ID = `${idPrefix}${index}`) */
    idPrefix?: string;
}

export function useListKeyboardNavigation({ itemCount, isOpen, onSelect, onClose, idPrefix }: UseListKeyboardNavigationOptions) {
    const [activeIndex, setActiveIndex] = useState(0);
    const [isKeyboardMode, setIsKeyboardMode] = useState(false);

    // Reset active index when list changes or opens/closes
    useEffect(() => {
        setActiveIndex(0);
    }, [itemCount, isOpen]);

    // Scroll active item into view
    useEffect(() => {
        if (idPrefix) {
            const el = document.getElementById(`${idPrefix}${activeIndex}`);
            if (el) el.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    }, [activeIndex, idPrefix]);

    const handleMouseEnter = useCallback((index: number) => {
        setIsKeyboardMode(false);
        setActiveIndex(index);
    }, []);

    const handleKeyDown = useCallback(
        (e: React.KeyboardEvent) => {
            if (!isOpen || itemCount === 0) return;

            if (e.key === "ArrowDown") {
                e.preventDefault();
                setIsKeyboardMode(true);
                setActiveIndex(prev => Math.min(prev + 1, itemCount - 1));
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setIsKeyboardMode(true);
                setActiveIndex(prev => Math.max(prev - 1, 0));
            } else if (e.key === "Enter" || e.key === "Tab") {
                e.preventDefault();
                onSelect(activeIndex);
            } else if (e.key === "Escape") {
                e.preventDefault();
                onClose?.();
            }
        },
        [isOpen, itemCount, activeIndex, onSelect, onClose]
    );

    return {
        activeIndex,
        isKeyboardMode,
        setActiveIndex,
        handleMouseEnter,
        handleKeyDown,
    };
}
