import React, { useState, useRef, useEffect, useCallback } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/esm/Page/AnnotationLayer.css";
import "react-pdf/dist/esm/Page/TextLayer.css";
import { ZoomIn, ZoomOut, ScanLine, Hand, Scissors } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui/tooltip";

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.mjs`;

interface PdfRendererProps {
    url: string;
    filename: string;
}

interface SelectionRect {
    startX: number;
    startY: number;
    endX: number;
    endY: number;
}

type InteractionMode = "text" | "pan" | "snip";

const pdfOptions = { withCredentials: true };

const PdfRenderer: React.FC<PdfRendererProps> = ({ url, filename }) => {
    const [numPages, setNumPages] = useState<number | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [zoomLevel, setZoomLevel] = useState(1);
    const [pan, setPan] = useState({ x: 0, y: 0 });
    const [isDragging, setIsDragging] = useState(false);
    const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
    const [pageWidth, setPageWidth] = useState<number | null>(null);
    const [interactionMode, setInteractionMode] = useState<InteractionMode>("text");
    const [selection, setSelection] = useState<SelectionRect | null>(null);
    const [isSelecting, setIsSelecting] = useState(false);
    const [copyStatus, setCopyStatus] = useState<"idle" | "copying" | "success" | "error">("idle");
    const viewerRef = useRef<HTMLDivElement>(null);
    const documentContainerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (pageWidth && viewerRef.current) {
            const containerWidth = viewerRef.current.clientWidth;
            const scale = (containerWidth - 40) / pageWidth;
            setZoomLevel(scale);
            setPan({ x: 0, y: 0 });
        }
    }, [pageWidth]);

    function onDocumentLoadSuccess({ numPages: nextNumPages }: { numPages: number }): void {
        setNumPages(nextNumPages);
        setError(null);
    }

    function onDocumentLoadError(error: Error): void {
        console.error("PDF load error:", error);
        let errorMessage = "Failed to load PDF. Please try downloading the file instead.";
        if (error.message?.includes("Invalid PDF structure")) {
            errorMessage = "This PDF file appears to be corrupted or has an invalid structure.";
        } else if (error.message?.includes("API version")) {
            errorMessage = "PDF viewer version mismatch. Please refresh the page.";
        } else if (error.message?.includes("Loading")) {
            errorMessage = "Unable to load the PDF file due to network issues or file corruption.";
        }
        setError(errorMessage);
    }

    const zoomIn = () => setZoomLevel(prev => Math.min(prev + 0.2, 3));
    const zoomOut = () => setZoomLevel(prev => Math.max(prev - 0.2, 0.2));

    const fitToPage = useCallback(() => {
        if (viewerRef.current && pageWidth) {
            const containerWidth = viewerRef.current.clientWidth;
            const scale = (containerWidth - 40) / pageWidth; // 20px padding on each side
            setZoomLevel(scale);
            setPan({ x: 0, y: 0 });
        }
    }, [pageWidth]);

    const handleMouseDown = (e: React.MouseEvent) => {
        if (e.button !== 0) return;

        if (interactionMode === "pan") {
            setIsDragging(true);
            setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
        } else if (interactionMode === "snip" && viewerRef.current) {
            const rect = viewerRef.current.getBoundingClientRect();
            const x = e.clientX - rect.left + viewerRef.current.scrollLeft;
            const y = e.clientY - rect.top + viewerRef.current.scrollTop;
            setSelection({ startX: x, startY: y, endX: x, endY: y });
            setIsSelecting(true);
        }
    };

    const handleMouseMove = (e: React.MouseEvent) => {
        if (interactionMode === "pan" && isDragging) {
            setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
        } else if (interactionMode === "snip" && isSelecting && viewerRef.current && selection) {
            const rect = viewerRef.current.getBoundingClientRect();
            const x = e.clientX - rect.left + viewerRef.current.scrollLeft;
            const y = e.clientY - rect.top + viewerRef.current.scrollTop;
            setSelection({ ...selection, endX: x, endY: y });
        }
    };

    const handleMouseUp = () => {
        if (interactionMode === "pan") {
            setIsDragging(false);
        } else if (interactionMode === "snip" && isSelecting) {
            setIsSelecting(false);
            // Auto-copy on mouse up if selection is valid
            if (selection) {
                const selWidth = Math.abs(selection.endX - selection.startX);
                const selHeight = Math.abs(selection.endY - selection.startY);
                if (selWidth >= 10 && selHeight >= 10) {
                    // Trigger copy immediately - the mouse up event is a user gesture
                    performSnipCopy();
                }
            }
        }
    };

    // Separate function to perform the snip copy, called directly from mouse up
    const performSnipCopy = async () => {
        if (!selection || !viewerRef.current) return;

        setCopyStatus("copying");

        try {
            // Calculate the normalized selection rectangle (in viewer scroll coordinates)
            const selX = Math.min(selection.startX, selection.endX);
            const selY = Math.min(selection.startY, selection.endY);
            const selWidth = Math.abs(selection.endX - selection.startX);
            const selHeight = Math.abs(selection.endY - selection.startY);

            // Find all canvas elements within the viewer
            const canvases = viewerRef.current.querySelectorAll("canvas");
            if (canvases.length === 0) {
                setCopyStatus("error");
                setTimeout(() => setCopyStatus("idle"), 2000);
                return;
            }

            // Create output canvas
            const outputCanvas = document.createElement("canvas");
            outputCanvas.width = selWidth;
            outputCanvas.height = selHeight;
            const ctx = outputCanvas.getContext("2d");

            if (!ctx) {
                setCopyStatus("error");
                setTimeout(() => setCopyStatus("idle"), 2000);
                return;
            }

            // Fill with white background
            ctx.fillStyle = "white";
            ctx.fillRect(0, 0, selWidth, selHeight);

            const viewerRect = viewerRef.current.getBoundingClientRect();
            const scrollLeft = viewerRef.current.scrollLeft;
            const scrollTop = viewerRef.current.scrollTop;

            // Process each canvas
            canvases.forEach(sourceCanvas => {
                const canvasRect = sourceCanvas.getBoundingClientRect();

                // Position of canvas in scroll coordinates
                const canvasScrollX = canvasRect.left - viewerRect.left + scrollLeft;
                const canvasScrollY = canvasRect.top - viewerRect.top + scrollTop;

                // Check intersection
                if (canvasScrollX + canvasRect.width <= selX || canvasScrollX >= selX + selWidth || canvasScrollY + canvasRect.height <= selY || canvasScrollY >= selY + selHeight) {
                    return; // No intersection
                }

                // Calculate the overlap region
                const overlapX1 = Math.max(selX, canvasScrollX);
                const overlapY1 = Math.max(selY, canvasScrollY);
                const overlapX2 = Math.min(selX + selWidth, canvasScrollX + canvasRect.width);
                const overlapY2 = Math.min(selY + selHeight, canvasScrollY + canvasRect.height);

                // Source coordinates (in the source canvas's coordinate system)
                const ratioX = sourceCanvas.width / canvasRect.width;
                const ratioY = sourceCanvas.height / canvasRect.height;

                const srcX = (overlapX1 - canvasScrollX) * ratioX;
                const srcY = (overlapY1 - canvasScrollY) * ratioY;
                const srcW = (overlapX2 - overlapX1) * ratioX;
                const srcH = (overlapY2 - overlapY1) * ratioY;

                // Destination coordinates (in the output canvas)
                const destX = overlapX1 - selX;
                const destY = overlapY1 - selY;
                const destW = overlapX2 - overlapX1;
                const destH = overlapY2 - overlapY1;

                ctx.drawImage(sourceCanvas, srcX, srcY, srcW, srcH, destX, destY, destW, destH);
            });

            // Convert canvas to data URL synchronously
            const dataUrl = outputCanvas.toDataURL("image/png");

            // Convert data URL to blob synchronously
            const arr = dataUrl.split(",");
            const mime = arr[0].match(/:(.*?);/)?.[1] || "image/png";
            const bstr = atob(arr[1]);
            let n = bstr.length;
            const u8arr = new Uint8Array(n);
            while (n--) {
                u8arr[n] = bstr.charCodeAt(n);
            }
            const blob = new Blob([u8arr], { type: mime });

            // Try to copy to clipboard
            let copied = false;
            try {
                if (navigator.clipboard && typeof ClipboardItem !== "undefined") {
                    const item = new ClipboardItem({ "image/png": blob });
                    await navigator.clipboard.write([item]);
                    copied = true;
                }
            } catch (clipboardErr) {
                console.error("Clipboard write failed:", clipboardErr);
                copied = false;
            }

            if (copied) {
                setCopyStatus("success");
                setTimeout(() => {
                    setCopyStatus("idle");
                    setSelection(null);
                }, 1500);
            } else {
                // Fallback: download the image
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `${filename}-snip.png`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                setCopyStatus("success");
                setTimeout(() => {
                    setCopyStatus("idle");
                    setSelection(null);
                }, 1500);
            }
        } catch (err) {
            console.error("Error capturing selection:", err);
            setCopyStatus("error");
            setTimeout(() => setCopyStatus("idle"), 2000);
        }
    };

    const setMode = (mode: InteractionMode) => {
        setInteractionMode(mode);
        setSelection(null);
        setCopyStatus("idle");
    };

    const handleWheel = (e: React.WheelEvent) => {
        // Only zoom when Ctrl/Cmd key is pressed, otherwise allow normal scrolling
        if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            if (e.deltaY < 0) {
                zoomIn();
            } else {
                zoomOut();
            }
        }
    };

    // Calculate selection rectangle for display
    const getSelectionStyle = (): React.CSSProperties | null => {
        if (!selection) return null;

        const x = Math.min(selection.startX, selection.endX);
        const y = Math.min(selection.startY, selection.endY);
        const width = Math.abs(selection.endX - selection.startX);
        const height = Math.abs(selection.endY - selection.startY);

        return {
            position: "absolute",
            left: x,
            top: y,
            width,
            height,
            border: "2px dashed #3b82f6",
            backgroundColor: "rgba(59, 130, 246, 0.1)",
            pointerEvents: "none",
            zIndex: 10,
        };
    };

    const getCursor = (): string => {
        if (interactionMode === "pan") {
            return isDragging ? "grabbing" : "grab";
        } else if (interactionMode === "snip") {
            return "crosshair";
        }
        return "auto";
    };

    if (error) {
        return (
            <div className="flex h-full flex-col overflow-auto p-4">
                <div className="flex flex-grow flex-col items-center justify-center text-center">
                    <div className="mb-4 p-4 text-red-500">{error}</div>
                    <a href={url} download={filename} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline dark:text-blue-400">
                        Download PDF
                    </a>
                </div>
            </div>
        );
    }

    return (
        <div className="flex h-full flex-col overflow-auto bg-gray-100 p-4 dark:bg-gray-800">
            <div className="mb-2 flex items-center justify-center">
                <div className="flex items-center gap-2 rounded-lg bg-white/80 px-3 py-1.5 shadow-sm backdrop-blur-sm dark:bg-gray-700/80">
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <button onClick={zoomOut} className="rounded p-1 hover:bg-gray-200 dark:hover:bg-gray-600">
                                <ZoomOut className="h-4 w-4" />
                            </button>
                        </TooltipTrigger>
                        <TooltipContent>Zoom Out</TooltipContent>
                    </Tooltip>
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <button onClick={zoomIn} className="rounded p-1 hover:bg-gray-200 dark:hover:bg-gray-600">
                                <ZoomIn className="h-4 w-4" />
                            </button>
                        </TooltipTrigger>
                        <TooltipContent>Zoom In</TooltipContent>
                    </Tooltip>
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <button onClick={fitToPage} className="rounded p-1 hover:bg-gray-200 dark:hover:bg-gray-600">
                                <ScanLine className="h-4 w-4" />
                            </button>
                        </TooltipTrigger>
                        <TooltipContent>Fit to Width</TooltipContent>
                    </Tooltip>
                    <div className="mx-1 h-4 w-px bg-gray-300 dark:bg-gray-600" />
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <button
                                onClick={() => setMode(interactionMode === "pan" ? "text" : "pan")}
                                className={`rounded p-1 ${interactionMode === "pan" ? "bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-300" : "hover:bg-gray-200 dark:hover:bg-gray-600"}`}
                            >
                                <Hand className="h-4 w-4" />
                            </button>
                        </TooltipTrigger>
                        <TooltipContent>{interactionMode === "pan" ? "Exit Pan Mode" : "Pan Mode"}</TooltipContent>
                    </Tooltip>
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <button
                                onClick={() => setMode(interactionMode === "snip" ? "text" : "snip")}
                                className={`rounded p-1 ${interactionMode === "snip" ? "bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-300" : "hover:bg-gray-200 dark:hover:bg-gray-600"}`}
                            >
                                <Scissors className="h-4 w-4" />
                            </button>
                        </TooltipTrigger>
                        <TooltipContent>{interactionMode === "snip" ? "Exit Snip Mode" : "Snip to Clipboard"}</TooltipContent>
                    </Tooltip>
                    {/* Show copy status indicator */}
                    {interactionMode === "snip" && copyStatus !== "idle" && (
                        <div
                            className={`ml-2 rounded px-2 py-0.5 text-xs ${
                                copyStatus === "copying"
                                    ? "bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-300"
                                    : copyStatus === "success"
                                      ? "bg-green-100 text-green-600 dark:bg-green-900 dark:text-green-300"
                                      : "bg-red-100 text-red-600 dark:bg-red-900 dark:text-red-300"
                            }`}
                        >
                            {copyStatus === "copying" ? "Copying..." : copyStatus === "success" ? "Copied!" : "Failed"}
                        </div>
                    )}
                </div>
            </div>
            <div
                ref={viewerRef}
                className={`relative w-full flex-grow overflow-auto rounded border border-gray-300 bg-gray-50 dark:border-gray-700 dark:bg-gray-900 ${interactionMode === "text" ? "select-text" : ""}`}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                onWheel={handleWheel}
                style={{ cursor: getCursor() }}
            >
                {/* Selection overlay */}
                {selection && getSelectionStyle() && <div style={getSelectionStyle()!} />}

                <Document
                    options={pdfOptions}
                    file={url}
                    onLoadSuccess={onDocumentLoadSuccess}
                    onLoadError={onDocumentLoadError}
                    loading={<div className="p-4 text-center">Loading PDF...</div>}
                    error={<div className="p-4 text-center text-red-500">Failed to load PDF.</div>}
                >
                    <div ref={documentContainerRef} style={{ transform: `translate(${pan.x}px, ${pan.y}px)` }}>
                        {numPages &&
                            Array.from(new Array(numPages), (_, index) => (
                                <div key={`page_${index + 1}`} className="flex justify-center p-2">
                                    <Page
                                        pageNumber={index + 1}
                                        scale={zoomLevel}
                                        onLoadSuccess={(page: { width: number }) => {
                                            if (index === 0 && !pageWidth) {
                                                setPageWidth(page.width);
                                            }
                                        }}
                                        renderTextLayer={interactionMode === "text"}
                                        renderAnnotationLayer={true}
                                        className="shadow-lg"
                                    />
                                </div>
                            ))}
                    </div>
                </Document>
            </div>
        </div>
    );
};

export default PdfRenderer;
