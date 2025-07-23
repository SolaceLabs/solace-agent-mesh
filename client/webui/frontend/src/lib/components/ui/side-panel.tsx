import * as React from "react";
import { cn } from "@/lib/utils";
import { useResizable } from "@/lib/components/ui/hooks";

export interface SidePanelProps {
    children: React.ReactNode;
    defaultWidth?: number;
    minWidth?: number;
    maxWidth?: number;
    position?: "left" | "right";
    resizable?: boolean;
    className?: string;
    onWidthChange?: (width: number) => void;
}

const SidePanel = React.forwardRef<HTMLDivElement, SidePanelProps>(({ children, defaultWidth = 300, minWidth = 200, maxWidth = 800, position = "left", resizable = true, className, onWidthChange, ...props }, ref) => {
    const { width, isResizing, handleMouseDown, handleTouchStart } = useResizable({
        defaultWidth,
        minWidth,
        maxWidth,
        position,
        onWidthChange,
    });

    const panelStyle = {
        width: `${width}px`,
    };

    const resizeHandlePosition = position === "left" ? "right-0" : "left-0";
    const resizeHandleCursor = "cursor-col-resize";

    return (
        <div
            ref={ref}
            className={cn(
                // Base layout classes
                "relative h-full flex-shrink-0 cursor-pointer",
                // Position-specific border
                position === "left" ? "border-r" : "border-l",
                className
            )}
            style={panelStyle}
            {...props}
        >
            {/* Main content area */}
            <div className={cn("h-full overflow-x-hidden overflow-y-auto")}>{children}</div>

            {/* Resize handle */}
            {resizable && (
                <div
                    className={cn(
                        "group absolute top-0 bottom-0 w-2",
                        resizeHandlePosition,
                        resizeHandleCursor,
                        // Visual feedback
                        "hover:bg-[var(--color-primary-wMain)]",
                        "transition-all duration-200",
                        // Active state
                        isResizing && "bg-[var(--color-primary-wMain)]"
                    )}
                    onMouseDown={handleMouseDown}
                    onTouchStart={handleTouchStart}
                    role="separator"
                    aria-orientation="vertical"
                    aria-label={`Resize ${position} panel`}
                    tabIndex={0}
                    onKeyDown={e => {
                        // Allow keyboard resize with arrow keys
                        if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
                            e.preventDefault();
                            const delta = e.key === "ArrowRight" ? 10 : -10;
                            const adjustedDelta = position === "right" ? -delta : delta;
                            const newWidth = Math.min(Math.max(width + adjustedDelta, minWidth), maxWidth);
                            onWidthChange?.(newWidth);
                        }
                    }}
                >
                    {/* Visual resize indicator */}
                    <div
                        className={cn(
                            "absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 transform",
                            "bg-[var(--color-secondary-w40)] dark:bg-[var(--color-secondary-w70)]",
                            "group-hover:bg-[var(--color-primary-wMain)]",
                            "transition-colors duration-200",
                            isResizing && "bg-[var(--color-primary-wMain)]"
                        )}
                    />
                </div>
            )}
        </div>
    );
});

SidePanel.displayName = "SidePanel";

export { SidePanel };
