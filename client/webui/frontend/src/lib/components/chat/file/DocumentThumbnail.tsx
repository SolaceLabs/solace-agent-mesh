import React, { useState, useEffect, useCallback, useContext, useRef } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { Loader2 } from "lucide-react";
import { ConfigContext } from "@/lib/contexts/ConfigContext";
import { cn } from "@/lib/utils";

// Configure PDF.js worker (same as PdfRenderer)
pdfjs.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.mjs`;

interface DocumentThumbnailProps {
    /** Base64-encoded content of the document */
    content: string;
    /** Filename with extension */
    filename: string;
    /** MIME type of the document */
    mimeType?: string;
    /** Width of the thumbnail in pixels */
    width?: number;
    /** Height of the thumbnail in pixels */
    height?: number;
    /** Additional CSS classes */
    className?: string;
    /** Callback when thumbnail fails to load */
    onError?: () => void;
    /** Callback when thumbnail loads successfully */
    onLoad?: () => void;
}

interface ConversionResponse {
    pdfContent: string;
    success: boolean;
    error: string | null;
}

// Cache for converted PDFs and thumbnails to avoid re-converting
const thumbnailCache = new Map<string, string>();

// Simple hash function for cache key
const hashContent = (content: string, filename: string): string => {
    // Use first 50 chars + length + filename for a quick hash
    const sample = content.substring(0, 50);
    return `thumb:${filename}:${content.length}:${sample}`;
};

// Check if file is a PDF
const isPdf = (filename: string, mimeType?: string): boolean => {
    if (mimeType === "application/pdf") return true;
    return filename.toLowerCase().endsWith(".pdf");
};

// Check if file is an Office document that can be converted
const isOfficeDocument = (filename: string, mimeType?: string): boolean => {
    const ext = filename.toLowerCase().split(".").pop();
    const officeExtensions = ["docx", "doc", "pptx", "ppt", "xlsx", "xls", "odt", "odp", "ods"];
    if (ext && officeExtensions.includes(ext)) return true;

    const officeMimeTypes = [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "application/vnd.oasis.opendocument.text",
        "application/vnd.oasis.opendocument.presentation",
        "application/vnd.oasis.opendocument.spreadsheet",
    ];
    return mimeType ? officeMimeTypes.includes(mimeType) : false;
};

// Check if file supports thumbnail generation
export const supportsThumbnail = (filename: string, mimeType?: string): boolean => {
    return isPdf(filename, mimeType) || isOfficeDocument(filename, mimeType);
};

const pdfOptions = { withCredentials: true };

/**
 * DocumentThumbnail - Renders a thumbnail preview of the first page of a document.
 *
 * Supports:
 * - PDF files (rendered directly using react-pdf)
 * - Office documents (DOCX, PPTX, etc.) - converted to PDF first using the backend service
 *
 * Falls back gracefully if conversion is not available or fails.
 */
export const DocumentThumbnail: React.FC<DocumentThumbnailProps> = ({ content, filename, mimeType, width = 52, height = 67, className, onError, onLoad }) => {
    const config = useContext(ConfigContext);
    const [pdfDataUrl, setPdfDataUrl] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [pageLoaded, setPageLoaded] = useState(false);
    const mountedRef = useRef(true);

    // Check if binary artifact preview is enabled via feature flag
    const binaryArtifactPreviewEnabled = config?.binaryArtifactPreviewEnabled ?? false;

    // Convert Office document to PDF using the backend service
    const convertToPdf = useCallback(
        async (base64Content: string): Promise<string | null> => {
            try {
                const response = await fetch("/api/v1/document-conversion/to-pdf", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    credentials: "include",
                    body: JSON.stringify({
                        content: base64Content,
                        filename: filename,
                    }),
                });

                if (!response.ok) {
                    console.warn("Document conversion failed:", response.status);
                    return null;
                }

                const data: ConversionResponse = await response.json();

                if (!data.success || !data.pdfContent) {
                    console.warn("Conversion returned no content:", data.error);
                    return null;
                }

                return data.pdfContent;
            } catch (err) {
                console.warn("Failed to convert document to PDF for thumbnail:", err);
                return null;
            }
        },
        [filename]
    );

    // Initialize thumbnail
    useEffect(() => {
        mountedRef.current = true;

        const initializeThumbnail = async () => {
            if (!content) {
                setIsLoading(false);
                setError("No content provided");
                onError?.();
                return;
            }

            // Check cache first
            const cacheKey = hashContent(content, filename);
            const cachedPdf = thumbnailCache.get(cacheKey);

            if (cachedPdf) {
                setPdfDataUrl(cachedPdf);
                setIsLoading(false);
                return;
            }

            setIsLoading(true);
            setError(null);

            try {
                let pdfBase64: string | null = null;

                if (isPdf(filename, mimeType)) {
                    // Content is already PDF
                    pdfBase64 = content;
                } else if (isOfficeDocument(filename, mimeType)) {
                    // Need to convert to PDF first
                    if (!binaryArtifactPreviewEnabled) {
                        if (mountedRef.current) {
                            setError("Preview not enabled");
                            setIsLoading(false);
                            onError?.();
                        }
                        return;
                    }

                    pdfBase64 = await convertToPdf(content);

                    if (!pdfBase64) {
                        if (mountedRef.current) {
                            setError("Conversion failed");
                            setIsLoading(false);
                            onError?.();
                        }
                        return;
                    }
                } else {
                    if (mountedRef.current) {
                        setError("Unsupported format");
                        setIsLoading(false);
                        onError?.();
                    }
                    return;
                }

                if (!mountedRef.current) return;

                // Create data URL for the PDF
                const dataUrl = `data:application/pdf;base64,${pdfBase64}`;

                // Cache the result
                thumbnailCache.set(cacheKey, dataUrl);

                setPdfDataUrl(dataUrl);
                setIsLoading(false);
            } catch (err) {
                console.error("Error initializing thumbnail:", err);
                if (mountedRef.current) {
                    setError("Failed to load");
                    setIsLoading(false);
                    onError?.();
                }
            }
        };

        initializeThumbnail();

        return () => {
            mountedRef.current = false;
        };
    }, [content, filename, mimeType, binaryArtifactPreviewEnabled, convertToPdf, onError]);

    // Handle page load success
    const handlePageLoadSuccess = useCallback(() => {
        setPageLoaded(true);
        onLoad?.();
    }, [onLoad]);

    // Handle page load error
    const handlePageLoadError = useCallback(() => {
        setError("Failed to render");
        onError?.();
    }, [onError]);

    // Loading state
    if (isLoading) {
        return (
            <div className={cn("bg-muted/50 flex items-center justify-center", className)} style={className?.includes("h-full") || className?.includes("w-full") ? undefined : { width, height }}>
                <Loader2 className="text-muted-foreground h-4 w-4 animate-spin" />
            </div>
        );
    }

    // Error state - return null to let parent show fallback
    if (error || !pdfDataUrl) {
        return null;
    }

    // Calculate scale to fit the thumbnail dimensions
    // We'll render at a fixed scale and let CSS handle the sizing
    const scale = 0.15; // Small scale for thumbnail

    return (
        <div className={cn("relative overflow-hidden bg-white", className)} style={className?.includes("h-full") || className?.includes("w-full") ? undefined : { width, height }}>
            {/* Show loading spinner while page is loading */}
            {!pageLoaded && (
                <div className="bg-muted/50 absolute inset-0 flex items-center justify-center">
                    <Loader2 className="text-muted-foreground h-3 w-3 animate-spin" />
                </div>
            )}
            <div className={cn("h-full w-full transition-opacity duration-200", !pageLoaded && "opacity-0")}>
                <Document file={pdfDataUrl} options={pdfOptions} loading={null} error={null} onLoadError={handlePageLoadError} className="thumbnail-document">
                    <Page pageNumber={1} scale={scale} renderTextLayer={false} renderAnnotationLayer={false} onLoadSuccess={handlePageLoadSuccess} onLoadError={handlePageLoadError} className="thumbnail-page" />
                </Document>
            </div>
            <style>{`
                .thumbnail-document {
                    width: 100% !important;
                    height: 100% !important;
                    display: flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                }
                .thumbnail-page {
                    width: 100% !important;
                    height: 100% !important;
                    display: flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                }
                .thumbnail-page canvas {
                    width: 100% !important;
                    height: 100% !important;
                    object-fit: cover !important;
                    object-position: top center !important;
                }
            `}</style>
        </div>
    );
};

export default DocumentThumbnail;
