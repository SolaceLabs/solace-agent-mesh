import type { FC } from "react";
import { ZoomIn, ZoomOut, Scan } from "lucide-react";
import { Button } from "../ui/button";

export interface CanvasControlsProps {
    /** Current zoom level as a decimal (e.g., 0.83 for 83%) */
    zoomLevel: number;
    /** Callback to zoom in */
    onZoomIn: () => void;
    /** Callback to zoom out */
    onZoomOut: () => void;
    /** Callback to fit/center the diagram */
    onFitToView: () => void;
    /** Minimum zoom level (for disabling zoom out) */
    minZoom?: number;
    /** Maximum zoom level (for disabling zoom in) */
    maxZoom?: number;
}

/**
 * CanvasControls - Control bar for pan/zoom canvas operations
 * Displays zoom level and provides zoom in/out and fit-to-view buttons
 */
export const CanvasControls: FC<CanvasControlsProps> = ({ zoomLevel, onZoomIn, onZoomOut, onFitToView, minZoom = 0.25, maxZoom = 2 }) => {
    // Format zoom level as percentage
    const zoomPercentage = Math.round(zoomLevel * 100);

    // Determine if buttons should be disabled
    const isAtMinZoom = zoomLevel <= minZoom;
    const isAtMaxZoom = zoomLevel >= maxZoom;

    return (
        <div className="flex items-center justify-end gap-2 border-b px-4 py-2">
            <Button onClick={onFitToView} variant="ghost" size="sm" tooltip="Center Workflow">
                <Scan className="h-4 w-4" />
            </Button>
            <div className="h-6 w-px border-l" />
            <div className="flex items-center gap-1">
                {/* Zoom out button */}
                <Button onClick={onZoomOut} disabled={isAtMinZoom} variant="ghost" size="sm" tooltip="Zoom out (10%)">
                    <ZoomOut className="h-4 w-4" />
                </Button>

                {/* Zoom level display */}
                <span className="min-w-[3.5rem] text-center text-sm font-medium">{zoomPercentage}%</span>

                {/* Zoom in button */}
                <Button onClick={onZoomIn} disabled={isAtMaxZoom} variant="ghost" size="sm" tooltip="Zoom in (10%)">
                    <ZoomIn className="h-4 w-4" />
                </Button>
            </div>
        </div>
    );
};

export default CanvasControls;
