import React, { useState, useEffect, useCallback, useContext } from "react";
import { FileType, Loader2, Download } from "lucide-react";
import PdfRenderer from "./PdfRenderer";
import { ConfigContext } from "@/lib/contexts/ConfigContext";

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

// Cache for converted PDFs to avoid re-converting on tab switches
// Key: hash of content + filename, Value: PDF data URL
const pdfConversionCache = new Map<string, string>();

// Simple hash function for cache key
const hashContent = (content: string, filename: string): string => {
    // Use first 100 chars + length + filename for a quick hash
    const sample = content.substring(0, 100);
    return `${filename}:${content.length}:${sample}`;
};

/**
 * OfficeDocumentRenderer - Renders Office documents (DOCX, PPTX) using PDF conversion.
 *
 * This component converts documents to PDF using the server-side LibreOffice conversion service.
 * If conversion is not available or fails, it shows a message to download the file.
 */
export const OfficeDocumentRenderer: React.FC<OfficeDocumentRendererProps> = ({ content, filename, documentType, setRenderError }) => {
    const config = useContext(ConfigContext);
    const [isCheckingService, setIsCheckingService] = useState(true);
    const [isConverting, setIsConverting] = useState(false);
    const [pdfDataUrl, setPdfDataUrl] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    // Check if binary artifact preview is enabled via feature flag
    const binaryArtifactPreviewEnabled = config?.binaryArtifactPreviewEnabled ?? false;

    // Check if document conversion service is available
    const checkConversionService = useCallback(async (): Promise<boolean> => {
        try {
            const response = await fetch("/api/v1/document-conversion/status", {
                credentials: "include",
            });

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
            console.warn("Failed to check document conversion service:", err);
            return false;
        }
    }, [documentType]);

    // Convert document to PDF
    const convertToPdf = useCallback(async (): Promise<string | null> => {
        try {
            const response = await fetch("/api/v1/document-conversion/to-pdf", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                credentials: "include",
                body: JSON.stringify({
                    content: content,
                    filename: filename,
                }),
            });

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
            console.error("Failed to convert document to PDF:", err);
            throw err;
        }
    }, [content, filename]);

    // Main effect to check service and convert
    useEffect(() => {
        let isMounted = true;

        const initializeRenderer = async () => {
            // Check if feature is enabled first
            if (!binaryArtifactPreviewEnabled) {
                console.log("Binary artifact preview is disabled via feature flag");
                setIsCheckingService(false);
                setError("Document preview is not enabled on this server.");
                return;
            }

            // Check cache first
            const cacheKey = hashContent(content, filename);
            const cachedPdf = pdfConversionCache.get(cacheKey);

            if (cachedPdf) {
                console.log("Using cached PDF conversion for:", filename);
                setPdfDataUrl(cachedPdf);
                setIsCheckingService(false);
                setIsConverting(false);
                return;
            }

            setIsCheckingService(true);
            setError(null);
            setPdfDataUrl(null);

            try {
                // Check if conversion service is available
                const isAvailable = await checkConversionService();

                if (!isMounted) return;

                setIsCheckingService(false);

                if (!isAvailable) {
                    setError("Document preview requires LibreOffice to be installed on the server.");
                    return;
                }

                // Try to convert to PDF
                setIsConverting(true);

                try {
                    const pdfUrl = await convertToPdf();

                    if (!isMounted) return;

                    if (pdfUrl) {
                        // Cache the result
                        pdfConversionCache.set(cacheKey, pdfUrl);
                        console.log("Cached PDF conversion for:", filename);
                        setPdfDataUrl(pdfUrl);
                    } else {
                        setError("Conversion returned no content.");
                    }
                } catch (convError) {
                    if (!isMounted) return;

                    console.error("PDF conversion failed:", convError);
                    setError(convError instanceof Error ? convError.message : "Conversion failed.");
                } finally {
                    if (isMounted) {
                        setIsConverting(false);
                    }
                }
            } catch (err) {
                if (!isMounted) return;

                console.error("Error initializing document renderer:", err);
                setIsCheckingService(false);
                setError("Failed to initialize document preview.");
            }
        };

        if (content) {
            initializeRenderer();
        }

        return () => {
            isMounted = false;
        };
    }, [content, filename, checkConversionService, convertToPdf, binaryArtifactPreviewEnabled]);

    // Propagate errors to parent
    useEffect(() => {
        if (error) {
            setRenderError(error);
        }
    }, [error, setRenderError]);

    // Loading state while checking service or converting
    if (isCheckingService || isConverting) {
        return (
            <div className="flex h-64 flex-col items-center justify-center space-y-4 text-center">
                <Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
                <div>
                    <p className="text-muted-foreground">Loading preview...</p>
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
