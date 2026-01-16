import React, { useState, useRef, useEffect, useCallback } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/esm/Page/AnnotationLayer.css";
import "react-pdf/dist/esm/Page/TextLayer.css";
import { ZoomIn, ZoomOut, RotateCcw, Maximize2 } from "lucide-react";

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.mjs`;

interface PdfRendererProps {
    url: string;
    filename: string;
}

const pdfOptions = { withCredentials: true };

const PdfRenderer: React.FC<PdfRendererProps> = ({ url, filename }) => {
    const [numPages, setNumPages] = useState<number | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [zoomLevel, setZoomLevel] = useState(1);
    const [pan, setPan] = useState({ x: 0, y: 0 });
    const [isDragging, setIsDragging] = useState(false);
    const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
    const [pageWidth, setPageWidth] = useState<number | null>(null);
    const viewerRef = useRef<HTMLDivElement>(null);

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
    const resetZoom = () => {
        setZoomLevel(1);
        setPan({ x: 0, y: 0 });
    };

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
        setIsDragging(true);
        setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    };

    const handleMouseMove = (e: React.MouseEvent) => {
        if (isDragging) {
            setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
        }
    };

    const handleMouseUp = () => setIsDragging(false);

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

    if (error) {
        return (
            <div className="flex h-full flex-col overflow-auto p-4">
                <h5 className="mb-2 self-start text-sm font-semibold">{`Preview: ${filename}`}</h5>
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
            <div className="mb-2 flex items-center justify-between">
                <h5 className="text-sm font-semibold">{`Preview: ${filename}`}</h5>
                <div className="flex items-center gap-2">
                    <button onClick={zoomOut} title="Zoom Out" className="rounded p-1 hover:bg-gray-200 dark:hover:bg-gray-700">
                        <ZoomOut className="h-4 w-4" />
                    </button>
                    <button onClick={resetZoom} title="Reset Zoom" className="rounded p-1 hover:bg-gray-200 dark:hover:bg-gray-700">
                        <RotateCcw className="h-4 w-4" />
                    </button>
                    <button onClick={zoomIn} title="Zoom In" className="rounded p-1 hover:bg-gray-200 dark:hover:bg-gray-700">
                        <ZoomIn className="h-4 w-4" />
                    </button>
                    <button onClick={fitToPage} title="Fit to Page" className="rounded p-1 hover:bg-gray-200 dark:hover:bg-gray-700">
                        <Maximize2 className="h-4 w-4" />
                    </button>
                </div>
            </div>
            <div
                ref={viewerRef}
                className="w-full flex-grow overflow-auto rounded border border-gray-300 bg-gray-50 dark:border-gray-700 dark:bg-gray-900"
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                onWheel={handleWheel}
                style={{ cursor: isDragging ? "grabbing" : "grab" }}
            >
                <Document
                    options={pdfOptions}
                    file={url}
                    onLoadSuccess={onDocumentLoadSuccess}
                    onLoadError={onDocumentLoadError}
                    loading={<div className="p-4 text-center">Loading PDF...</div>}
                    error={<div className="p-4 text-center text-red-500">Failed to load PDF.</div>}
                >
                    <div style={{ transform: `translate(${pan.x}px, ${pan.y}px)` }}>
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
                                        renderTextLayer={true}
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
