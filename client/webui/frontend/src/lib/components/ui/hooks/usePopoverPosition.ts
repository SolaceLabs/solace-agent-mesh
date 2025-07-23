import { useCallback } from "react";

export type PopoverPlacement = "top" | "bottom" | "left" | "right" | "top-start" | "top-end" | "bottom-start" | "bottom-end" | "left-start" | "left-end" | "right-start" | "right-end";

interface PopoverOffset {
    x: number;
    y: number;
}

interface UsePopoverPositionProps {
    anchorRef: React.RefObject<HTMLElement | null>;
    placement?: PopoverPlacement;
    offset?: PopoverOffset;
    fallbackPlacements?: PopoverPlacement[];
}

interface PopoverPosition {
    top: number;
    left: number;
    placement: PopoverPlacement;
}

const DEFAULT_OFFSET = { x: 0, y: 0 };
const VIEWPORT_PADDING = 16;
const FALLBACK_PLACEMENTS: PopoverPlacement[] = ["top-start", "bottom-end", "top-end"];

export function usePopoverPosition({ anchorRef, placement = "top-start", offset = DEFAULT_OFFSET, fallbackPlacements = FALLBACK_PLACEMENTS }: UsePopoverPositionProps) {
    const calculatePosition = useCallback(
        (anchorRect: DOMRect, popoverRect: DOMRect, targetPlacement: PopoverPlacement): PopoverPosition => {
            let top = 0;
            let left = 0;

            // Calculate base position based on placement
            switch (targetPlacement) {
                case "top":
                    top = anchorRect.top - popoverRect.height - offset.y;
                    left = anchorRect.left + (anchorRect.width - popoverRect.width) / 2 + offset.x;
                    break;
                case "top-start":
                    top = anchorRect.top - popoverRect.height - offset.y;
                    left = anchorRect.left + offset.x;
                    break;
                case "top-end":
                    top = anchorRect.top - popoverRect.height - offset.y;
                    left = anchorRect.right - popoverRect.width - offset.x;
                    break;
                case "bottom":
                    top = anchorRect.bottom + offset.y;
                    left = anchorRect.left + (anchorRect.width - popoverRect.width) / 2 + offset.x;
                    break;
                case "bottom-start":
                    top = anchorRect.bottom + offset.y;
                    left = anchorRect.left + offset.x;
                    break;
                case "bottom-end":
                    top = anchorRect.bottom + offset.y;
                    left = anchorRect.right - popoverRect.width - offset.x;
                    break;
                case "left":
                    top = anchorRect.top + (anchorRect.height - popoverRect.height) / 2 + offset.y;
                    left = anchorRect.left - popoverRect.width - offset.x;
                    break;
                case "left-start":
                    top = anchorRect.top + offset.y;
                    left = anchorRect.left - popoverRect.width - offset.x;
                    break;
                case "left-end":
                    top = anchorRect.bottom - popoverRect.height - offset.y;
                    left = anchorRect.left - popoverRect.width - offset.x;
                    break;
                case "right":
                    top = anchorRect.top + (anchorRect.height - popoverRect.height) / 2 + offset.y;
                    left = anchorRect.right + offset.x;
                    break;
                case "right-start":
                    top = anchorRect.top + offset.y;
                    left = anchorRect.right + offset.x;
                    break;
                case "right-end":
                    top = anchorRect.bottom - popoverRect.height - offset.y;
                    left = anchorRect.right + offset.x;
                    break;
            }

            console.log(`Calculated position for ${targetPlacement}:`, { top, left });

            return { top, left, placement: targetPlacement };
        },
        [offset.x, offset.y]
    );

    const checkCollision = useCallback((position: PopoverPosition, popoverRect: DOMRect): boolean => {
        const viewport = {
            width: window.innerWidth,
            height: window.innerHeight,
        };

        return position.left < VIEWPORT_PADDING || position.top < VIEWPORT_PADDING || position.left + popoverRect.width > viewport.width - VIEWPORT_PADDING || position.top + popoverRect.height > viewport.height - VIEWPORT_PADDING;
    }, []);

    const getOptimalPosition = useCallback(
        (popoverElement: HTMLElement): PopoverPosition => {
            if (!anchorRef.current) {
                // Fallback to center of viewport if no anchor
                const viewport = {
                    width: window.innerWidth,
                    height: window.innerHeight,
                };
                return {
                    top: viewport.height / 2 - 100,
                    left: viewport.width / 2 - 100,
                    placement,
                };
            }

            const anchorRect = anchorRef.current.getBoundingClientRect();
            const popoverRect = popoverElement.getBoundingClientRect();

            // Try primary placement first
            const primaryPosition = calculatePosition(anchorRect, popoverRect, placement);

            if (!checkCollision(primaryPosition, popoverRect)) {
                return primaryPosition;
            }

            // Try fallback placements
            for (const fallbackPlacement of fallbackPlacements) {
                const fallbackPosition = calculatePosition(anchorRect, popoverRect, fallbackPlacement);

                if (!checkCollision(fallbackPosition, popoverRect)) {
                    return fallbackPosition;
                }
            }

            // If all placements have collisions, use the primary placement with adjustments
            const viewport = {
                width: window.innerWidth,
                height: window.innerHeight,
            };

            const adjustedPosition = { ...primaryPosition };

            // Adjust horizontal position
            if (adjustedPosition.left < VIEWPORT_PADDING) {
                adjustedPosition.left = VIEWPORT_PADDING;
            } else if (adjustedPosition.left + popoverRect.width > viewport.width - VIEWPORT_PADDING) {
                adjustedPosition.left = viewport.width - popoverRect.width - VIEWPORT_PADDING;
            }

            // Adjust vertical position
            if (adjustedPosition.top < VIEWPORT_PADDING) {
                adjustedPosition.top = VIEWPORT_PADDING;
            } else if (adjustedPosition.top + popoverRect.height > viewport.height - VIEWPORT_PADDING) {
                adjustedPosition.top = viewport.height - popoverRect.height - VIEWPORT_PADDING;
            }

            return adjustedPosition;
        },
        [anchorRef, placement, fallbackPlacements, calculatePosition, checkCollision]
    );

    const getPositionStyle = useCallback(
        (popoverElement: HTMLElement): React.CSSProperties => {
            const position = getOptimalPosition(popoverElement);

            return {
                position: "fixed",
                top: position.top,
                left: position.left,
                zIndex: 1000,
            };
        },
        [getOptimalPosition]
    );

    return {
        getPositionStyle,
        getOptimalPosition,
    };
}
