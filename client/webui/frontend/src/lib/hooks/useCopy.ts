import { useRef } from "react";
import type { KeyboardEvent, RefObject } from "react";

interface UseCopyReturn<T extends HTMLElement> {
    ref: RefObject<T | null>;
    handleKeyDown: (e: KeyboardEvent) => void;
    selectAllContent: () => void;
}

/**
 * A custom hook that provides a ref and keydown handler for selecting content to copy it.
 */
export function useCopy<T extends HTMLElement>(): UseCopyReturn<T> {
    const ref = useRef<T>(null);

    const selectAllContent = () => {
        if (ref.current) {
            const range = document.createRange();
            range.selectNodeContents(ref.current);
            const selection = window.getSelection();
            if (selection) {
                selection.removeAllRanges();
                selection.addRange(range);
            }
        }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
        // Handle cmd-a / ctrl-a
        if ((e.metaKey || e.ctrlKey) && e.key === "a") {
            e.preventDefault();
            selectAllContent();
        }
    };

    return {
        ref,
        handleKeyDown,
        selectAllContent,
    };
}
