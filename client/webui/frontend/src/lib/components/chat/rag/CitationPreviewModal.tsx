import React, { useState, useMemo } from "react";
import { ExternalLink, Loader2, AlertCircle } from "lucide-react";

import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, VisuallyHidden } from "@/lib/components/ui/dialog";
import { Button } from "@/lib/components/ui/button";
import { FileIcon } from "@/lib/components/chat/file/FileIcon";
import { ContentRenderer } from "@/lib/components/chat/preview/ContentRenderer";
import { useDocumentContent } from "@/lib/api/documents";
import { useProjectContext } from "@/lib/providers/ProjectProvider";
import { getArtifactUrl } from "@/lib/utils/file";
import { getRenderType, decodeBase64Content } from "@/lib/components/chat/preview/previewUtils";
import { highlightCitationsInText, getFirstCitationPreview } from "@/lib/utils/highlightUtils";
import type { RAGSource } from "@/lib/types";

export interface CitationPreviewModalProps {
    isOpen: boolean;
    onClose: () => void;
    filename: string;
    pageLabel: string;
    pageNumber: number;
    sourceIndex: number;
    fileExtension: string;
    citations: RAGSource[];
}

/**
 * Modal for previewing document citations.
 * Displays the document content with highlighted citations (for text files)
 * or scrolls to the relevant page (for PDFs).
 */
export const CitationPreviewModal: React.FC<CitationPreviewModalProps> = ({ isOpen, onClose, filename, pageLabel, pageNumber, sourceIndex, fileExtension, citations }) => {
    const { activeProject } = useProjectContext();
    const projectId = activeProject?.id ?? null;

    const [renderError, setRenderError] = useState<string | null>(null);

    // Fetch document content when modal is open
    const { data: documentData, isLoading, error: fetchError } = useDocumentContent(isOpen ? projectId : null, isOpen ? filename : null);

    // Determine render type from filename
    const renderType = useMemo(() => getRenderType(filename, documentData?.mimeType), [filename, documentData?.mimeType]);

    // Build URL for PDF rendering and file download
    const fileUrl = useMemo(() => {
        if (!projectId) return null;
        try {
            return getArtifactUrl({ filename, projectId });
        } catch {
            return null;
        }
    }, [filename, projectId]);

    // Process content for text-based files (apply highlighting)
    const processedContent = useMemo(() => {
        if (!documentData?.content || !renderType) return "";

        // For URL-based renderers (PDF), we don't need to process content
        if (renderType === "pdf") return "";

        // Decode base64 content
        let decodedContent: string;
        try {
            decodedContent = decodeBase64Content(documentData.content);
        } catch {
            return documentData.content;
        }

        // Apply highlighting for text-based content
        if (["text", "markdown"].includes(renderType)) {
            return highlightCitationsInText(decodedContent, citations);
        }

        return decodedContent;
    }, [documentData?.content, renderType, citations]);

    // Get first citation preview for PDF files (shown in header)
    const citationPreview = useMemo(() => {
        if (renderType !== "pdf") return null;
        return getFirstCitationPreview(citations);
    }, [renderType, citations]);

    const handleViewFile = () => {
        if (fileUrl) {
            window.open(fileUrl, "_blank", "noopener,noreferrer");
        }
    };

    const error = fetchError || renderError;

    return (
        <Dialog open={isOpen} onOpenChange={open => !open && onClose()}>
            <DialogContent className="flex h-[85vh] max-h-[900px] w-[90vw] max-w-5xl flex-col">
                {/* Header */}
                <DialogHeader className="flex-none border-b pb-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <FileIcon filename={filename} variant="compact" />
                            <div className="flex flex-col gap-0.5">
                                <DialogTitle className="text-base font-semibold">Source {sourceIndex + 1}</DialogTitle>
                                <DialogDescription className="text-muted-foreground text-sm">
                                    {pageLabel} · {fileExtension.toUpperCase()} file
                                </DialogDescription>
                            </div>
                        </div>
                        {fileUrl && (
                            <Button variant="outline" size="sm" onClick={handleViewFile}>
                                <ExternalLink className="mr-1.5 h-4 w-4" />
                                View File
                            </Button>
                        )}
                    </div>

                    {/* Citation preview for PDFs */}
                    {citationPreview && (
                        <div className="mt-3 rounded-md bg-amber-50 p-3 dark:bg-amber-900/20">
                            <p className="text-sm font-medium text-amber-800 dark:text-amber-200">Cited Text:</p>
                            <p className="mt-1 text-sm text-amber-700 italic dark:text-amber-300">"{citationPreview}"</p>
                        </div>
                    )}
                </DialogHeader>

                {/* Content */}
                <div className="relative flex-1 overflow-hidden">
                    {isLoading && (
                        <div className="flex h-full items-center justify-center">
                            <Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
                            <span className="text-muted-foreground ml-2">Loading document...</span>
                        </div>
                    )}

                    {error && (
                        <div className="text-destructive flex h-full flex-col items-center justify-center gap-2">
                            <AlertCircle className="h-8 w-8" />
                            <p className="text-sm">{error instanceof Error ? error.message : String(error)}</p>
                        </div>
                    )}

                    {!isLoading && !error && renderType && (
                        <div className="h-full overflow-auto">
                            {renderType === "pdf" && fileUrl ? (
                                <ContentRenderer content="" rendererType={renderType} mime_type={documentData?.mimeType} url={fileUrl} filename={filename} setRenderError={setRenderError} initialPage={pageNumber} />
                            ) : renderType === "text" || renderType === "markdown" ? (
                                // Use dangerouslySetInnerHTML for highlighted text content
                                <div className="h-full overflow-auto p-4">
                                    <pre className="whitespace-pre-wrap select-text focus-visible:outline-none" style={{ overflowWrap: "anywhere" }} dangerouslySetInnerHTML={{ __html: processedContent }} />
                                </div>
                            ) : (
                                <ContentRenderer content={processedContent} rendererType={renderType} mime_type={documentData?.mimeType} setRenderError={setRenderError} />
                            )}
                        </div>
                    )}

                    {!isLoading && !error && !renderType && (
                        <div className="text-muted-foreground flex h-full flex-col items-center justify-center gap-2">
                            <AlertCircle className="h-8 w-8" />
                            <p className="text-sm">Preview not available for this file type</p>
                            {fileUrl && (
                                <Button variant="link" onClick={handleViewFile}>
                                    Download file instead
                                </Button>
                            )}
                        </div>
                    )}
                </div>

                {/* Footer */}
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
