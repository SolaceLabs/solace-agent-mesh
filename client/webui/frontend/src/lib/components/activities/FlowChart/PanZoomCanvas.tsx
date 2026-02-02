import React, { useRef, useState, useCallback, useEffect } from "react";

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
    /** Zoom in by 10% (rounded to nearest 10%), centered on viewport */
    zoomIn: (options?: { animated?: boolean }) => void;
    /** Zoom out by 10% (rounded to nearest 10%), centered on viewport */
    zoomOut: (options?: { animated?: boolean }) => void;
    /** Zoom to a specific scale, centered on viewport or specified point */
    zoomTo: (scale: number, options?: { animated?: boolean; centerX?: number; centerY?: number }) => void;
    /** Pan to center a point (in content coordinates) in the viewport */
    panToPoint: (contentX: number, contentY: number, options?: { animated?: boolean }) => void;
}

interface PointerState {
    x: number;
    y: number;
}

interface GestureState {
    centerX: number;
    centerY: number;
    distance: number;
}

const PanZoomCanvas = React.forwardRef<PanZoomCanvasRef, PanZoomCanvasProps>(({ children, initialScale = 1, minScale = 0.1, maxScale = 4, onTransformChange, onUserInteraction, sidePanelWidth = 0 }, ref) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [transform, setTransform] = useState({
        scale: initialScale,
        x: 0,
        y: 0,
    });
    const [isAnimating, setIsAnimating] = useState(false);

    // Track active pointers for multi-touch
    const pointersRef = useRef<Map<number, PointerState>>(new Map());
    const lastGestureRef = useRef<GestureState | null>(null);
    const isDraggingRef = useRef(false);
    const lastDragPosRef = useRef<{ x: number; y: number } | null>(null);

    // Clamp scale within bounds (defined early for use in ref methods)
    const clampScale = useCallback((scale: number) => Math.min(Math.max(scale, minScale), maxScale), [minScale, maxScale]);

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
            const fitMaxScale = options?.maxFitScale ?? 1.0;
            const scaleToFitWidth = (availableWidth - padding) / contentWidth;
            const newScale = Math.min(Math.max(scaleToFitWidth, minScale), fitMaxScale);

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
        zoomIn: (options?: { animated?: boolean }) => {
            const container = containerRef.current;
            if (!container) return;

            const rect = container.getBoundingClientRect();
            // Zoom toward center of viewport (accounting for side panel)
            const centerX = (rect.width - sidePanelWidth) / 2;
            const centerY = rect.height / 2;

            setTransform(prev => {
                // Round to nearest 10% and add 10%
                const currentPercent = Math.round(prev.scale * 100);
                const roundedPercent = Math.round(currentPercent / 10) * 10;
                const targetPercent = Math.min(roundedPercent + 10, maxScale * 100);
                const newScale = clampScale(targetPercent / 100);
                const scaleRatio = newScale / prev.scale;

                // Zoom toward center
                const newX = centerX - (centerX - prev.x) * scaleRatio;
                const newY = centerY - (centerY - prev.y) * scaleRatio;

                return { scale: newScale, x: newX, y: newY };
            });

            if (options?.animated) {
                setIsAnimating(true);
                setTimeout(() => setIsAnimating(false), 300);
            }
        },
        zoomOut: (options?: { animated?: boolean }) => {
            const container = containerRef.current;
            if (!container) return;

            const rect = container.getBoundingClientRect();
            // Zoom toward center of viewport (accounting for side panel)
            const centerX = (rect.width - sidePanelWidth) / 2;
            const centerY = rect.height / 2;

            setTransform(prev => {
                // Round to nearest 10% and subtract 10%
                const currentPercent = Math.round(prev.scale * 100);
                const roundedPercent = Math.round(currentPercent / 10) * 10;
                const targetPercent = Math.max(roundedPercent - 10, minScale * 100);
                const newScale = clampScale(targetPercent / 100);
                const scaleRatio = newScale / prev.scale;

                // Zoom toward center
                const newX = centerX - (centerX - prev.x) * scaleRatio;
                const newY = centerY - (centerY - prev.y) * scaleRatio;

                return { scale: newScale, x: newX, y: newY };
            });

            if (options?.animated) {
                setIsAnimating(true);
                setTimeout(() => setIsAnimating(false), 300);
            }
        },
        zoomTo: (targetScale: number, options?: { animated?: boolean; centerX?: number; centerY?: number }) => {
            const container = containerRef.current;
            if (!container) return;

            const rect = container.getBoundingClientRect();
            // Use provided center or viewport center
            const centerX = options?.centerX ?? (rect.width - sidePanelWidth) / 2;
            const centerY = options?.centerY ?? rect.height / 2;

            const newScale = clampScale(targetScale);

            setTransform(prev => {
                const scaleRatio = newScale / prev.scale;
                const newX = centerX - (centerX - prev.x) * scaleRatio;
                const newY = centerY - (centerY - prev.y) * scaleRatio;
                return { scale: newScale, x: newX, y: newY };
            });

            if (options?.animated) {
                setIsAnimating(true);
                setTimeout(() => setIsAnimating(false), 300);
            }
        },
        panToPoint: (contentX: number, contentY: number, options?: { animated?: boolean }) => {
            const container = containerRef.current;
            if (!container) return;

            const rect = container.getBoundingClientRect();
            // Calculate viewport center (accounting for side panel)
            const viewportCenterX = (rect.width - sidePanelWidth) / 2;
            const viewportCenterY = rect.height / 2;

            setTransform(prev => {
                // Convert content coordinates to screen coordinates at current scale
                // Then calculate the offset needed to center that point
                const newX = viewportCenterX - contentX * prev.scale;
                const newY = viewportCenterY - contentY * prev.scale;
                return { ...prev, x: newX, y: newY };
            });

            if (options?.animated) {
                setIsAnimating(true);
                setTimeout(() => setIsAnimating(false), 300);
            }
        },
    }));

    // Notify parent of transform changes
    useEffect(() => {
        onTransformChange?.(transform);
    }, [transform, onTransformChange]);

    // Calculate gesture state from two pointers
    const calculateGestureState = useCallback((pointers: Map<number, PointerState>): GestureState | null => {
        const points = Array.from(pointers.values());
        if (points.length < 2) return null;

        const [p1, p2] = points;
        const centerX = (p1.x + p2.x) / 2;
        const centerY = (p1.y + p2.y) / 2;
        const distance = Math.sqrt(Math.pow(p2.x - p1.x, 2) + Math.pow(p2.y - p1.y, 2));

        return { centerX, centerY, distance };
    }, []);

    // Handle pointer down
    const handlePointerDown = useCallback(
        (e: React.PointerEvent) => {
            // Capture the pointer for tracking
            (e.target as HTMLElement).setPointerCapture(e.pointerId);

            pointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });

            if (pointersRef.current.size === 1) {
                // Single pointer - start drag
                isDraggingRef.current = true;
                lastDragPosRef.current = { x: e.clientX, y: e.clientY };
            } else if (pointersRef.current.size === 2) {
                // Two pointers - start pinch gesture
                isDraggingRef.current = false;
                lastDragPosRef.current = null;
                lastGestureRef.current = calculateGestureState(pointersRef.current);
            }
        },
        [calculateGestureState]
    );

    // Handle pointer move
    const handlePointerMove = useCallback(
        (e: React.PointerEvent) => {
            if (!pointersRef.current.has(e.pointerId)) return;

            // Update pointer position
            pointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });

            const rect = containerRef.current?.getBoundingClientRect();
            if (!rect) return;

            if (pointersRef.current.size >= 2) {
                // Multi-touch: calculate pan AND zoom simultaneously
                const currentGesture = calculateGestureState(pointersRef.current);
                const lastGesture = lastGestureRef.current;

                if (currentGesture && lastGesture) {
                    // Pan: movement of the center point (average finger displacement)
                    const panDeltaX = currentGesture.centerX - lastGesture.centerX;
                    const panDeltaY = currentGesture.centerY - lastGesture.centerY;

                    // Zoom: change in distance between fingers
                    const zoomFactor = currentGesture.distance / lastGesture.distance;

                    // Pinch center relative to container
                    const cursorX = currentGesture.centerX - rect.left;
                    const cursorY = currentGesture.centerY - rect.top;

                    setTransform(prev => {
                        const newScale = clampScale(prev.scale * zoomFactor);
                        const scaleRatio = newScale / prev.scale;

                        // Apply zoom toward pinch center
                        let newX = cursorX - (cursorX - prev.x) * scaleRatio;
                        let newY = cursorY - (cursorY - prev.y) * scaleRatio;

                        // Apply pan from finger movement (simultaneously!)
                        newX += panDeltaX;
                        newY += panDeltaY;

                        return { scale: newScale, x: newX, y: newY };
                    });

                    onUserInteraction?.();
                }

                lastGestureRef.current = currentGesture;
            } else if (isDraggingRef.current && lastDragPosRef.current) {
                // Single pointer drag - pan only
                const dx = e.clientX - lastDragPosRef.current.x;
                const dy = e.clientY - lastDragPosRef.current.y;

                setTransform(prev => ({
                    ...prev,
                    x: prev.x + dx,
                    y: prev.y + dy,
                }));

                lastDragPosRef.current = { x: e.clientX, y: e.clientY };
                onUserInteraction?.();
            }
        },
        [calculateGestureState, clampScale, onUserInteraction]
    );

    // Handle pointer up/cancel
    const handlePointerUp = useCallback((e: React.PointerEvent) => {
        (e.target as HTMLElement).releasePointerCapture(e.pointerId);
        pointersRef.current.delete(e.pointerId);

        if (pointersRef.current.size < 2) {
            lastGestureRef.current = null;
        }

        if (pointersRef.current.size === 1) {
            // Went from 2 to 1 pointer - switch to drag mode
            const remaining = Array.from(pointersRef.current.values())[0];
            isDraggingRef.current = true;
            lastDragPosRef.current = { x: remaining.x, y: remaining.y };
        } else if (pointersRef.current.size === 0) {
            isDraggingRef.current = false;
            lastDragPosRef.current = null;
        }
    }, []);

    // Handle wheel events (mouse wheel zoom + trackpad gestures)
    // Must be added manually with { passive: false } to allow preventDefault()
    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;

        const handleWheel = (e: WheelEvent) => {
            e.preventDefault();

            const rect = container.getBoundingClientRect();

            const dx = e.deltaX;
            const dy = e.deltaY;
            const ctrlKey = e.ctrlKey || e.metaKey;
            const shiftKey = e.shiftKey;

            // Check if this looks like a trackpad 2-finger swipe (has horizontal component)
            const isTrackpadSwipe = Math.abs(dx) > 1 && !ctrlKey;

            if (shiftKey) {
                // Shift+scroll -> pan horizontally
                setTransform(prev => ({
                    ...prev,
                    x: prev.x - dy,
                }));
                onUserInteraction?.();
            } else if (ctrlKey) {
                // Trackpad pinch -> zoom + pan
                const zoomFactor = 1 - dy * 0.01;
                const cursorX = e.clientX - rect.left;
                const cursorY = e.clientY - rect.top;

                setTransform(prev => {
                    const newScale = clampScale(prev.scale * zoomFactor);
                    const scaleRatio = newScale / prev.scale;

                    let newX = cursorX - (cursorX - prev.x) * scaleRatio;
                    const newY = cursorY - (cursorY - prev.y) * scaleRatio;
                    newX -= dx;

                    return { scale: newScale, x: newX, y: newY };
                });
                onUserInteraction?.();
            } else if (isTrackpadSwipe) {
                // Trackpad 2-finger swipe -> pan
                setTransform(prev => ({
                    ...prev,
                    x: prev.x - dx,
                    y: prev.y - dy,
                }));
                onUserInteraction?.();
            } else {
                // Mouse wheel -> zoom toward cursor
                const zoomFactor = 1 - dy * 0.005;
                const cursorX = e.clientX - rect.left;
                const cursorY = e.clientY - rect.top;

                setTransform(prev => {
                    const newScale = clampScale(prev.scale * zoomFactor);
                    const scaleRatio = newScale / prev.scale;

                    const newX = cursorX - (cursorX - prev.x) * scaleRatio;
                    const newY = cursorY - (cursorY - prev.y) * scaleRatio;

                    return { scale: newScale, x: newX, y: newY };
                });
                onUserInteraction?.();
            }
        };

        // Add with passive: false to allow preventDefault()
        container.addEventListener("wheel", handleWheel, { passive: false });

        return () => {
            container.removeEventListener("wheel", handleWheel);
        };
    }, [clampScale, onUserInteraction]);

    // Handle double-click to zoom in at click location
    const handleDoubleClick = useCallback(
        (e: React.MouseEvent) => {
            // Prevent text selection on double-click
            e.preventDefault();

            // Only handle if clicking on the container background (not on interactive nodes)
            // Check if the click target is a button, link, or has data-no-zoom attribute
            const target = e.target as HTMLElement;
            if (target.closest("button") || target.closest("a") || target.closest("[data-no-zoom]") || target.closest("[role='button']")) {
                return;
            }

            const rect = containerRef.current?.getBoundingClientRect();
            if (!rect) return;

            const cursorX = e.clientX - rect.left;
            const cursorY = e.clientY - rect.top;

            // Zoom in by 10% toward click location
            setTransform(prev => {
                const currentPercent = Math.round(prev.scale * 100);
                const roundedPercent = Math.round(currentPercent / 10) * 10;
                const targetPercent = Math.min(roundedPercent + 10, maxScale * 100);
                const newScale = clampScale(targetPercent / 100);
                const scaleRatio = newScale / prev.scale;

                const newX = cursorX - (cursorX - prev.x) * scaleRatio;
                const newY = cursorY - (cursorY - prev.y) * scaleRatio;

                return { scale: newScale, x: newX, y: newY };
            });

            setIsAnimating(true);
            setTimeout(() => setIsAnimating(false), 300);
            onUserInteraction?.();
        },
        [clampScale, maxScale, onUserInteraction]
    );

    return (
        <div
            ref={containerRef}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onPointerCancel={handlePointerUp}
            onDoubleClick={handleDoubleClick}
            style={{
                width: "100%",
                height: "100%",
                overflow: "hidden",
                touchAction: "none",
                cursor: "grab",
                userSelect: "none",
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
});

PanZoomCanvas.displayName = "PanZoomCanvas";

export default PanZoomCanvas;
