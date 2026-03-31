import { useEffect } from "react";
import type { RefObject } from "react";

/**
 * Scrolls to the first highlighted element in a container after DOM paint.
 *
 * @param containerRef - Ref to the container element to search within
 * @param selector - CSS selector for the highlighted element (e.g., "mark", ".citation-highlight")
 * @param enabled - Whether scrolling is enabled
 * @param dependencies - Additional dependencies that should trigger the scroll
 */
export function useScrollToHighlight<T extends HTMLElement = HTMLElement>(containerRef: RefObject<T | null>, selector: string, enabled: boolean, dependencies: React.DependencyList = []): void {
    useEffect(() => {
        if (!enabled) return;

        // This ensures both ref attachment and innerHTML painting are complete
        requestAnimationFrame(() => {
            if (!containerRef.current) return;

            const firstHighlight = containerRef.current.querySelector(selector);
            if (firstHighlight) {
                firstHighlight.scrollIntoView({ behavior: "smooth", block: "center" });
            }
        });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [enabled, ...dependencies]);
}

/**
 * Utility function to scroll an element into view after the next browser paint.
 * Use this when you already have the element and just need to scroll to it.
 *
 * @param element - The element to scroll to
 * @param onComplete - Optional callback to run after scroll is initiated
 */
export function scrollToElement(element: Element, onComplete?: () => void): void {
    requestAnimationFrame(() => {
        element.scrollIntoView({ behavior: "smooth", block: "center" });
        onComplete?.();
    });
}
