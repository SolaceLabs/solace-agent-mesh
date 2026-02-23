import React, { useState, useMemo } from "react";
import DOMPurify from "dompurify";
import { AlertCircle } from "lucide-react";

import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, VisuallyHidden } from "@/lib/components/ui/dialog";
import { Button } from "@/lib/components/ui/button";
import { FileIcon } from "@/lib/components/chat/file/FileIcon";
import { ContentRenderer } from "@/lib/components/chat/preview/ContentRenderer";
import { LoadingState, ErrorState, NoPreviewState } from "@/lib/components/chat/preview/Renderers";
import { useDocumentContent } from "@/lib/api/documents";
import { useProjectContext } from "@/lib/providers/ProjectProvider";
import { getRenderType, decodeBase64Content } from "@/lib/components/chat/preview/previewUtils";
import { highlightCitationsInText, extractCitationTexts } from "@/lib/utils/highlightUtils";
import type { RAGSource } from "@/lib/types";
import type { CitationMapEntry } from "@/lib/components/chat/preview/Renderers/PdfRenderer";

export interface CitationPreviewModalProps {
    isOpen: boolean;
    onClose: () => void;
    filename: string;
    pageLabel: string;
    pageNumber: number;
    sourceIndex: number;
    citations: RAGSource[];
    fileExtension?: string;
}

/**
 * Modal for previewing document citations.
 * Displays the document content with highlighted citations (for text files)
 * or scrolls to the relevant page (for PDFs).
 */
export const CitationPreviewModal: React.FC<CitationPreviewModalProps> = ({ isOpen, onClose, filename, pageLabel, pageNumber, sourceIndex, citations }) => {
    const { activeProject } = useProjectContext();
    const projectId = activeProject?.id ?? null;

    const [renderError, setRenderError] = useState<string | null>(null);

    const { data: documentData, isLoading, error: fetchError } = useDocumentContent(isOpen ? projectId : null, isOpen ? filename : null);

    // For PDFs, prioritize filename extension over mimeType since backend may return
    // application/json wrapper which would incorrectly trigger JSON renderer
    const renderType = (() => {
        const lowerFilename = filename.toLowerCase();
        if (lowerFilename.endsWith(".pdf")) return "pdf";
        return getRenderType(filename, documentData?.mimeType);
    })();

    // Use "latest" version to get actual file content (without version, endpoint returns version list as JSON)
    const fileUrl = useMemo(() => {
        if (!projectId) return null;
        const encodedFilename = encodeURIComponent(filename);
        return `/api/v1/artifacts/null/${encodedFilename}/versions/latest?project_id=${projectId}`;
    }, [filename, projectId]);

    const highlightTexts = extractCitationTexts(citations);

    // Extract citation_map entries for precise character-position highlighting
    const citationMaps = useMemo((): CitationMapEntry[] => {
        return citations.flatMap(c => (c.metadata?.citation_map as CitationMapEntry[]) || []);
    }, [citations]);

    const processedContent = useMemo(() => {
        if (!documentData?.content || !renderType) return "";
        if (renderType === "pdf") return "";

        // For binary formats (docx, pptx), the OfficeDocumentRenderer expects base64-encoded content
        if (["docx", "pptx"].includes(renderType)) {
            return documentData.content;
        }

        let decodedContent: string;
        try {
            decodedContent = decodeBase64Content(documentData.content);
        } catch {
            return documentData.content;
        }

        if (["text", "markdown"].includes(renderType)) {
            const highlighted = highlightCitationsInText(decodedContent, citations);
            // Sanitize to prevent XSS while allowing <mark> tags for highlights
            return DOMPurify.sanitize(highlighted, { ALLOWED_TAGS: ["mark"], ALLOWED_ATTR: ["class"] });
        }

        return decodedContent;
    }, [documentData?.content, renderType, citations]);

    const handleViewFile = () => {
        if (fileUrl) {
            window.open(fileUrl, "_blank", "noopener,noreferrer");
        }
    };

    const error = fetchError || renderError;

    return (
        <Dialog open={isOpen} onOpenChange={open => !open && onClose()}>
            <DialogContent className="flex h-[80vh] min-w-[80vw] flex-col">
                <DialogHeader className="flex-none border-b pb-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <FileIcon filename={filename} variant="compact" />
                            <div className="flex flex-col gap-0.5">
                                <DialogTitle className="text-base font-semibold">Source {sourceIndex + 1}</DialogTitle>
                                <DialogDescription className="text-muted-foreground flex items-center gap-1.5 text-sm">{pageLabel}</DialogDescription>
                            </div>
                        </div>
                        {fileUrl && (
                            <Button variant="outline" size="sm" onClick={handleViewFile}>
                                View File
                            </Button>
                        )}
                    </div>
                </DialogHeader>

                <div className="relative flex-1 overflow-hidden">
                    {isLoading && <LoadingState message="Loading document..." />}

                    {error && <ErrorState message={error instanceof Error ? error.message : String(error)} />}

                    {!isLoading && !error && renderType && (
                        <div className="h-full overflow-auto">
                            {renderType === "pdf" ? (
                                fileUrl ? (
                                    <ContentRenderer
                                        content=""
                                        rendererType={renderType}
                                        mime_type={documentData?.mimeType}
                                        url={fileUrl}
                                        filename={filename}
                                        setRenderError={setRenderError}
                                        initialPage={pageNumber}
                                        highlightTexts={highlightTexts}
                                        citationMaps={citationMaps}
                                    />
                                ) : (
                                    <div className="text-muted-foreground flex h-full flex-col items-center justify-center gap-2">
                                        <AlertCircle className="h-8 w-8" />
                                        <p className="text-sm">Unable to preview PDF: No active project context</p>
                                    </div>
                                )
                            ) : renderType === "text" || renderType === "markdown" ? (
                                <div className="h-full overflow-auto p-4">
                                    <pre className="whitespace-pre-wrap select-text focus-visible:outline-none" style={{ overflowWrap: "anywhere" }} dangerouslySetInnerHTML={{ __html: processedContent }} />
                                </div>
                            ) : (
                                <ContentRenderer content={processedContent} rendererType={renderType} mime_type={documentData?.mimeType} setRenderError={setRenderError} highlightTexts={highlightTexts} />
                            )}
                        </div>
                    )}

                    {!isLoading && !error && !renderType && <NoPreviewState />}
                </div>

                <DialogFooter className="flex-none border-t pt-4">
                    <p className="text-muted-foreground flex-1 text-xs">This is a preview of the document containing the citation</p>
                    <Button variant="outline" onClick={onClose}>
                        Close
                    </Button>
                </DialogFooter>

                {/* Accessible title for screen readers */}
                <VisuallyHidden>
                    <DialogDescription>
                        Preview of {filename} showing citation from {pageLabel}
                    </DialogDescription>
                </VisuallyHidden>
            </DialogContent>
        </Dialog>
    );
};
