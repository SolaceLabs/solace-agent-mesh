import React, { useState, useEffect, useCallback, useContext, useRef } from "react";
import { FileType, Loader2, Download } from "lucide-react";
import PdfRenderer from "./PdfRenderer";
import { ConfigContext } from "@/lib/contexts/ConfigContext";
import { api } from "@/lib/api";

interface OfficeDocumentRendererProps {
    content: string;
    filename: string;
    documentType: "docx" | "pptx";
    setRenderError: (error: string | null) => void;
}

interface ConversionStatusResponse {
    available: boolean;
    supportedFormats: string[];
}

interface ConversionResponse {
    pdfContent: string;
    success: boolean;
    error: string | null;
}

// Request timeout in milliseconds (30 seconds)
const REQUEST_TIMEOUT_MS = 30000;

// LRU Cache for converted PDFs to avoid re-converting on tab switches
// Key: hash of content + filename, Value: PDF data URL
// Limited to prevent unbounded memory growth
const PDF_CACHE_MAX_ENTRIES = 10;

interface CacheEntry {
    value: string;
    lastAccessed: number;
}

class LRUCache {
    private cache = new Map<string, CacheEntry>();
    private maxSize: number;

    constructor(maxSize: number) {
        this.maxSize = maxSize;
    }

    get(key: string): string | undefined {
        const entry = this.cache.get(key);
        if (entry) {
            // Update last accessed time
            entry.lastAccessed = Date.now();
            return entry.value;
        }
        return undefined;
    }

    set(key: string, value: string): void {
        // If we're at capacity, remove least recently used
        if (this.cache.size >= this.maxSize && !this.cache.has(key)) {
            let oldestKey: string | null = null;
            let oldestTime = Infinity;

            for (const [k, v] of this.cache.entries()) {
                if (v.lastAccessed < oldestTime) {
                    oldestTime = v.lastAccessed;
                    oldestKey = k;
                }
            }

            if (oldestKey) {
                console.log("[OfficeDocumentRenderer] Evicting LRU cache entry to make room for new entry");
                this.cache.delete(oldestKey);
            }
        }

        this.cache.set(key, { value, lastAccessed: Date.now() });
    }

    has(key: string): boolean {
        return this.cache.has(key);
    }

    size(): number {
        return this.cache.size;
    }
}

const pdfConversionCache = new LRUCache(PDF_CACHE_MAX_ENTRIES);

// Improved hash function for cache key using djb2 algorithm
// Uses more content and includes a proper hash to reduce collision risk
const hashContent = (content: string, filename: string): string => {
    // Use djb2 hash algorithm on content sample
    const sampleSize = Math.min(content.length, 1000); // Use up to 1000 chars
    const sample = content.substring(0, sampleSize);

    let hash = 5381;
    for (let i = 0; i < sample.length; i++) {
        hash = (hash * 33) ^ sample.charCodeAt(i);
    }

    // Convert to unsigned 32-bit integer and then to base36 string
    const hashStr = (hash >>> 0).toString(36);

    // Include filename, content length, and hash for uniqueness
    return `${filename}:${content.length}:${hashStr}`;
};

/**
 * Fetch with timeout using AbortController.
 * Uses the api client (authenticatedFetch) which handles Bearer token auth and token refresh.
 * Falls back to cookie auth when no token is present (community mode).
 */
async function fetchWithTimeout(url: string, options: RequestInit, timeoutMs: number, signal?: AbortSignal): Promise<Response> {
    // Create a timeout abort controller
    const timeoutController = new AbortController();
    const timeoutId = setTimeout(() => timeoutController.abort(), timeoutMs);

    // Combine external abort signal with timeout signal
    const combinedSignal = signal ? AbortSignal.any([signal, timeoutController.signal]) : timeoutController.signal;

    const method = (options.method || "GET").toUpperCase();

    try {
        let response: Response;
        if (method === "POST") {
            // Parse body back to object so api client can re-serialize with Content-Type header
            const body = options.body ? JSON.parse(options.body as string) : undefined;
            response = await api.webui.post(url, body, {
                signal: combinedSignal,
                fullResponse: true,
            });
        } else {
            response = await api.webui.get(url, {
                signal: combinedSignal,
                fullResponse: true,
            });
        }
        return response;
    } finally {
        clearTimeout(timeoutId);
    }
}

/**
 * OfficeDocumentRenderer - Renders Office documents (DOCX, PPTX) using PDF conversion.
 *
 * This component converts documents to PDF using the server-side LibreOffice conversion service.
 * If conversion is not available or fails, it shows a message to download the file.
 *
 * Key features:
 * - Uses AbortController for proper request cancellation on unmount
 * - Prevents duplicate conversions via state tracking
 * - Caches converted PDFs to avoid re-conversion on tab switches
 * - Adds request timeout to prevent hung requests
 */
export const OfficeDocumentRenderer: React.FC<OfficeDocumentRendererProps> = ({ content, filename, documentType, setRenderError }) => {
    const config = useContext(ConfigContext);

    // Conversion state machine: 'idle' | 'checking' | 'converting' | 'success' | 'error'
    const [conversionState, setConversionState] = useState<"idle" | "checking" | "converting" | "success" | "error">("idle");
    const [pdfDataUrl, setPdfDataUrl] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    // Ref to track if we've already started conversion for this content
    // This prevents re-conversion if the effect runs multiple times
    const conversionStartedRef = useRef<string | null>(null);

    // Check if binary artifact preview is enabled via feature flag
    const binaryArtifactPreviewEnabled = config?.binaryArtifactPreviewEnabled ?? false;

    // Check if document conversion service is available
    const checkConversionService = useCallback(
        async (signal: AbortSignal): Promise<boolean> => {
            try {
                const response = await fetchWithTimeout("/api/v1/document-conversion/status", {}, REQUEST_TIMEOUT_MS, signal);

                if (!response.ok) {
                    console.warn("Document conversion service status check failed:", response.status);
                    return false;
                }

                const data: ConversionStatusResponse = await response.json();

                // Check if the service is available and supports our document type
                const extension = documentType;
                const isSupported = data.available && data.supportedFormats.includes(extension);

                console.log(`Document conversion service: available=${data.available}, supports ${extension}=${isSupported}`);
                return isSupported;
            } catch (err) {
                // Don't log abort errors - they're expected on unmount
                if (err instanceof Error && err.name === "AbortError") {
                    throw err; // Re-throw to be handled by caller
                }
                console.warn("Failed to check document conversion service:", err);
                return false;
            }
        },
        [documentType]
    );

    // Convert document to PDF
    const convertToPdf = useCallback(
        async (signal: AbortSignal): Promise<string | null> => {
            try {
                const response = await fetchWithTimeout(
                    "/api/v1/document-conversion/to-pdf",
                    {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            content: content,
                            filename: filename,
                        }),
                    },
                    REQUEST_TIMEOUT_MS,
                    signal
                );

                if (!response.ok) {
                    const errorText = await response.text();
                    console.error("Document conversion failed:", response.status, errorText);
                    throw new Error(`Conversion failed: ${response.status}`);
                }

                const data: ConversionResponse = await response.json();

                if (!data.success || !data.pdfContent) {
                    throw new Error(data.error || "Conversion returned no content");
                }

                // Create a data URL for the PDF content
                return `data:application/pdf;base64,${data.pdfContent}`;
            } catch (err) {
                // Don't log abort errors
                if (err instanceof Error && err.name === "AbortError") {
                    throw err;
                }
                console.error("Failed to convert document to PDF:", err);
                throw err;
            }
        },
        [content, filename]
    );

    // Main effect to check service and convert
    // Uses AbortController for proper cleanup instead of deprecated isMounted pattern
    useEffect(() => {
        // Create AbortController for this effect
        const abortController = new AbortController();
        const signal = abortController.signal;

        const initializeRenderer = async () => {
            // Generate cache key for this content
            const cacheKey = hashContent(content, filename);

            // Skip if we've already started conversion for this exact content
            // This prevents duplicate conversions on re-renders
            if (conversionStartedRef.current === cacheKey) {
                console.log("[OfficeDocumentRenderer] Skipping duplicate conversion for:", filename);
                return;
            }

            // Check if feature is enabled first
            if (!binaryArtifactPreviewEnabled) {
                console.log("Binary artifact preview is disabled via feature flag");
                setConversionState("error");
                setError("Document preview is not enabled on this server.");
                return;
            }

            // Check cache first
            const cachedPdf = pdfConversionCache.get(cacheKey);

            if (cachedPdf) {
                console.log("Using cached PDF conversion for:", filename);
                setPdfDataUrl(cachedPdf);
                setConversionState("success");
                return;
            }

            // Mark that we're starting conversion for this content
            conversionStartedRef.current = cacheKey;

            setConversionState("checking");
            setError(null);
            setPdfDataUrl(null);

            try {
                // Check if conversion service is available
                const isAvailable = await checkConversionService(signal);

                // Check if aborted
                if (signal.aborted) return;

                if (!isAvailable) {
                    setConversionState("error");
                    setError("Document preview requires LibreOffice to be installed on the server.");
                    return;
                }

                // Try to convert to PDF
                setConversionState("converting");

                try {
                    const pdfUrl = await convertToPdf(signal);

                    // Check if aborted
                    if (signal.aborted) return;

                    if (pdfUrl) {
                        // Cache the result
                        pdfConversionCache.set(cacheKey, pdfUrl);
                        console.log("Cached PDF conversion for:", filename);
                        setPdfDataUrl(pdfUrl);
                        setConversionState("success");
                    } else {
                        setConversionState("error");
                        setError("Conversion returned no content.");
                    }
                } catch (convError) {
                    // Check if aborted (component unmounted)
                    if (signal.aborted) return;
                    if (convError instanceof Error && convError.name === "AbortError") return;

                    console.error("PDF conversion failed:", convError);
                    setConversionState("error");

                    // Check for timeout error
                    if (convError instanceof Error && convError.message.includes("timeout")) {
                        setError("Conversion timed out. The document may be too large or complex.");
                    } else {
                        setError(convError instanceof Error ? convError.message : "Conversion failed.");
                    }
                }
            } catch (err) {
                // Check if aborted (component unmounted)
                if (signal.aborted) return;
                if (err instanceof Error && err.name === "AbortError") return;

                console.error("Error initializing document renderer:", err);
                setConversionState("error");
                setError("Failed to initialize document preview.");
            }
        };

        if (content) {
            initializeRenderer();
        }

        // Cleanup: abort any in-flight requests when component unmounts
        // or when dependencies change
        return () => {
            abortController.abort();
        };
    }, [content, filename, checkConversionService, convertToPdf, binaryArtifactPreviewEnabled]);

    // Propagate errors to parent
    useEffect(() => {
        if (error) {
            setRenderError(error);
        }
    }, [error, setRenderError]);

    // Loading state while checking service or converting
    if (conversionState === "checking" || conversionState === "converting") {
        return (
            <div className="flex h-64 flex-col items-center justify-center space-y-4 text-center">
                <Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
                <div>
                    <p className="text-muted-foreground">{conversionState === "checking" ? "Checking service availability..." : "Converting document to PDF..."}</p>
                </div>
            </div>
        );
    }

    // If we have a PDF URL, render using PdfRenderer
    if (pdfDataUrl) {
        return <PdfRenderer url={pdfDataUrl} filename={filename} />;
    }

    // Error state - show message to download the file
    return (
        <div className="flex h-64 flex-col items-center justify-center space-y-4 p-6 text-center">
            <FileType className="text-muted-foreground h-16 w-16" />
            <div>
                <h3 className="text-lg font-semibold">Preview Unavailable</h3>
                <p className="text-muted-foreground mt-2">Unable to preview this {documentType.toUpperCase()} file.</p>
                {error && <p className="text-muted-foreground mt-1 text-sm">{error}</p>}
                <p className="text-muted-foreground mt-4 flex items-center justify-center gap-2 text-sm">
                    <Download className="h-4 w-4" />
                    Download the file to open it in the appropriate application.
                </p>
            </div>
        </div>
    );
};

export default OfficeDocumentRenderer;
