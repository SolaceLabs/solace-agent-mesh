import type { KeyboardEvent, MouseEvent } from "react";

/**
 * Returns accessibility props for a clickable node div, including onClick with stopPropagation.
 */
export function clickableNodeProps(handler?: () => void) {
    const trigger = (e: MouseEvent | KeyboardEvent) => {
        e.stopPropagation();
        handler?.();
    };
    return {
        role: "button" as const,
        tabIndex: 0,
        onClick: (e: MouseEvent) => trigger(e),
        onKeyDown: (e: KeyboardEvent) => {
            if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                trigger(e);
            }
        },
    };
}
