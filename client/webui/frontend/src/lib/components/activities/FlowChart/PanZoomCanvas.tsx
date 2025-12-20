import React, { useRef, useState, useCallback, useEffect } from "react";
import { useGesture } from "@use-gesture/react";

interface PanZoomCanvasProps {
    children: React.ReactNode;
    initialScale?: number;
    minScale?: number;
    maxScale?: number;
    onTransformChange?: (transform: { scale: number; x: number; y: number }) => void;
    onUserInteraction?: () => void;
    /** Width of any side panel that reduces available viewport width */
    sidePanelWidth?: number;
}

export interface PanZoomCanvasRef {
    resetTransform: () => void;
    getTransform: () => { scale: number; x: number; y: number };
    /** Fit content to viewport, showing full width and top-aligned */
    fitToContent: (contentWidth: number, options?: { animated?: boolean; maxFitScale?: number }) => void;
}

const PanZoomCanvas = React.forwardRef<PanZoomCanvasRef, PanZoomCanvasProps>(
    (
        {
            children,
            initialScale = 1,
            minScale = 0.1,
            maxScale = 4,
            onTransformChange,
            onUserInteraction,
            sidePanelWidth = 0,
        },
        ref
    ) => {
        const containerRef = useRef<HTMLDivElement>(null);
        const [transform, setTransform] = useState({
            scale: initialScale,
            x: 0,
            y: 0,
        });
        const [isAnimating, setIsAnimating] = useState(false);

        // Expose methods via ref
        React.useImperativeHandle(ref, () => ({
            resetTransform: () => {
                setTransform({ scale: initialScale, x: 0, y: 0 });
            },
            getTransform: () => transform,
            fitToContent: (contentWidth: number, options?: { animated?: boolean; maxFitScale?: number }) => {
                const container = containerRef.current;
                if (!container) return;

                const rect = container.getBoundingClientRect();
                // Account for side panel width
                const availableWidth = rect.width - sidePanelWidth;

                // Padding around the content
                const padding = 80; // 40px on each side
                const topPadding = 60; // Extra space at top for controls

                // Calculate scale to fit width
                // Default max is 1.0 (don't zoom in), but can be overridden
                const maxScale = options?.maxFitScale ?? 1.0;
                const scaleToFitWidth = (availableWidth - padding) / contentWidth;
                const newScale = Math.min(Math.max(scaleToFitWidth, minScale), maxScale);

                // Center horizontally, align to top
                const scaledContentWidth = contentWidth * newScale;
                const newX = (availableWidth - scaledContentWidth) / 2;
                const newY = topPadding;

                if (options?.animated) {
                    setIsAnimating(true);
                    // Disable animation after transition completes
                    setTimeout(() => setIsAnimating(false), 300);
                }

                setTransform({ scale: newScale, x: newX, y: newY });
            },
        }));

        // Notify parent of transform changes
        useEffect(() => {
            onTransformChange?.(transform);
        }, [transform, onTransformChange]);

        // Clamp scale within bounds
        const clampScale = useCallback(
            (scale: number) => Math.min(Math.max(scale, minScale), maxScale),
            [minScale, maxScale]
        );

        // Handle gestures
        useGesture(
            {
                // Two-finger drag / trackpad scroll -> PAN
                onWheel: ({ delta: [dx, dy], event, ctrlKey }) => {
                    event.preventDefault();

                    // ctrlKey is true for pinch-to-zoom on trackpad (browser sends ctrl+wheel)
                    if (ctrlKey) {
                        // Pinch zoom on trackpad
                        const zoomFactor = 1 - dy * 0.01;
                        const rect = containerRef.current?.getBoundingClientRect();
                        if (!rect) return;

                        // Zoom toward cursor position
                        const cursorX = event.clientX - rect.left;
                        const cursorY = event.clientY - rect.top;

                        setTransform((prev) => {
                            const newScale = clampScale(prev.scale * zoomFactor);
                            const scaleRatio = newScale / prev.scale;

                            // Adjust position to zoom toward cursor
                            const newX = cursorX - (cursorX - prev.x) * scaleRatio;
                            const newY = cursorY - (cursorY - prev.y) * scaleRatio;

                            return { scale: newScale, x: newX, y: newY };
                        });
                        onUserInteraction?.();
                    } else {
                        // Regular scroll -> pan
                        setTransform((prev) => ({
                            ...prev,
                            x: prev.x - dx,
                            y: prev.y - dy,
                        }));
                        onUserInteraction?.();
                    }
                },

                // Click and drag -> PAN
                onDrag: ({ delta: [dx, dy], event }) => {
                    // Only pan with left mouse button or touch
                    if (event instanceof MouseEvent && event.button !== 0) return;

                    setTransform((prev) => ({
                        ...prev,
                        x: prev.x + dx,
                        y: prev.y + dy,
                    }));
                    onUserInteraction?.();
                },

                // Pinch gesture (touch devices) -> ZOOM
                onPinch: ({ offset: [scale], origin: [ox, oy], event }) => {
                    event?.preventDefault();
                    const rect = containerRef.current?.getBoundingClientRect();
                    if (!rect) return;

                    const cursorX = ox - rect.left;
                    const cursorY = oy - rect.top;

                    setTransform((prev) => {
                        const newScale = clampScale(scale);
                        const scaleRatio = newScale / prev.scale;

                        // Adjust position to zoom toward pinch center
                        const newX = cursorX - (cursorX - prev.x) * scaleRatio;
                        const newY = cursorY - (cursorY - prev.y) * scaleRatio;

                        return { scale: newScale, x: newX, y: newY };
                    });
                    onUserInteraction?.();
                },
            },
            {
                target: containerRef,
                wheel: {
                    eventOptions: { passive: false },
                },
                drag: {
                    filterTaps: true,
                    pointer: { mouse: true, touch: true },
                },
                pinch: {
                    scaleBounds: { min: minScale, max: maxScale },
                    eventOptions: { passive: false },
                },
            }
        );

        return (
            <div
                ref={containerRef}
                style={{
                    width: "100%",
                    height: "100%",
                    overflow: "hidden",
                    touchAction: "none",
                    cursor: "grab",
                }}
            >
                <div
                    style={{
                        transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
                        transformOrigin: "0 0",
                        width: "fit-content",
                        height: "fit-content",
                        transition: isAnimating ? "transform 300ms ease-out" : "none",
                    }}
                >
                    {children}
                </div>
            </div>
        );
    }
);

PanZoomCanvas.displayName = "PanZoomCanvas";

export default PanZoomCanvas;
