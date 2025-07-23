import React, { useRef, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";
import { useClickOutside, useEscapeKey, usePopoverPosition, type PopoverPlacement } from "@/lib/components/ui";

interface PopoverProps {
    isOpen: boolean;
    onClose: () => void;
    anchorRef: React.RefObject<HTMLElement | null>;
    children: React.ReactNode;
    placement?: PopoverPlacement;
    offset?: { x: number; y: number };
    className?: string;
    closeOnClickOutside?: boolean;
    closeOnEscape?: boolean;
    portal?: boolean;
    animationDuration?: number;
    fallbackPlacements?: PopoverPlacement[];
}

export function PopoverManual({ isOpen, onClose, anchorRef, children, placement = "bottom-start", offset, className, closeOnClickOutside = true, closeOnEscape = true, portal = true, animationDuration = 150, fallbackPlacements }: PopoverProps) {
    const popoverRef = useRef<HTMLDivElement>(null);
    const [positionStyle, setPositionStyle] = useState<React.CSSProperties>({});
    const [isPositioned, setIsPositioned] = useState(false);

    // Use our custom hooks
    useClickOutside({
        ref: popoverRef,
        anchorRef,
        onClickOutside: onClose,
        enabled: isOpen && closeOnClickOutside,
    });

    useEscapeKey({
        onEscape: onClose,
        enabled: isOpen && closeOnEscape,
    });

    const { getPositionStyle: calculatePosition } = usePopoverPosition({
        anchorRef,
        placement,
        offset,
        fallbackPlacements,
    });

    // Calculate position when popover opens
    useEffect(() => {
        if (isOpen && popoverRef.current) {
            setIsPositioned(false);

            // Single requestAnimationFrame is sufficient for positioning
            requestAnimationFrame(() => {
                if (popoverRef.current) {
                    const newPositionStyle = calculatePosition(popoverRef.current);
                    setPositionStyle(newPositionStyle);
                    setIsPositioned(true);
                }
            });
        } else {
            setIsPositioned(false);
        }
    }, [isOpen, calculatePosition]);

    // Don't render if not open
    if (!isOpen) {
        return null;
    }

    const popoverContent = (
        <div
            ref={popoverRef}
            role="dialog"
            aria-modal="false"
            className={cn("bg-background min-w-[8rem] overflow-hidden border shadow-md", className)}
            style={{
                ...positionStyle,
                opacity: isOpen && isPositioned ? 1 : 0,
                transform: `scale(${isOpen && isPositioned ? 1 : 0.95})`,
                transition: `opacity ${animationDuration}ms ease-in-out, transform ${animationDuration}ms ease-in-out`,
                pointerEvents: isOpen && isPositioned ? "auto" : "none",
                visibility: isPositioned ? "visible" : "hidden",
            }}
        >
            {children}
        </div>
    );

    if (portal) {
        return createPortal(popoverContent, document.body);
    }

    return popoverContent;
}
