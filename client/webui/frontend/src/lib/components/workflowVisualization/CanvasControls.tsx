import type { FC } from "react";
import { ZoomIn, ZoomOut, Home } from "lucide-react";

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
            {/* Fit to view / Center button */}
            <button
                onClick={onFitToView}
                className="flex h-8 w-8 items-center justify-center rounded p-0 text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-700 dark:hover:text-gray-100"
                title="Fit diagram to view"
            >
                <Home className="h-4 w-4" />
            </button>

            {/* Separator */}
            <div className="h-6 w-px bg-gray-200 dark:bg-gray-700" />

            {/* Zoom controls group */}
            <div className="flex items-center gap-1">
                {/* Zoom out button */}
                <button
                    onClick={onZoomOut}
                    disabled={isAtMinZoom}
                    className="flex h-8 w-8 items-center justify-center rounded p-0 text-gray-600 hover:bg-gray-100 hover:text-gray-900 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent dark:text-gray-400 dark:hover:bg-gray-700 dark:hover:text-gray-100"
                    title="Zoom out (10%)"
                >
                    <ZoomOut className="h-4 w-4" />
                </button>

                {/* Zoom level display */}
                <span className="min-w-[3.5rem] text-center text-sm font-medium text-gray-700 dark:text-gray-300">{zoomPercentage}%</span>

                {/* Zoom in button */}
                <button
                    onClick={onZoomIn}
                    disabled={isAtMaxZoom}
                    className="flex h-8 w-8 items-center justify-center rounded p-0 text-gray-600 hover:bg-gray-100 hover:text-gray-900 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent dark:text-gray-400 dark:hover:bg-gray-700 dark:hover:text-gray-100"
                    title="Zoom in (10%)"
                >
                    <ZoomIn className="h-4 w-4" />
                </button>
            </div>
        </div>
    );
};

export default CanvasControls;
