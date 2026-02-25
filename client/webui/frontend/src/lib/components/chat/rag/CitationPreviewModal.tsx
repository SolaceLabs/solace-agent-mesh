import React, { useState, useMemo } from "react";
import DOMPurify from "dompurify";

import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, VisuallyHidden } from "@/lib/components/ui/dialog";
import { Button } from "@/lib/components/ui/button";
import { FileIcon } from "@/lib/components/chat/file/FileIcon";
import { ContentRenderer } from "@/lib/components/chat/preview/ContentRenderer";
import { NoPreviewState } from "@/lib/components/chat/preview/Renderers";
import { EmptyState } from "@/lib/components/common/EmptyState";
import { MessageBanner } from "@/lib/components/common/MessageBanner";
import { useArtifactContent } from "@/lib/api/artifacts";
import { useProjectContext } from "@/lib/providers/ProjectProvider";
import { getRenderType, decodeBase64Content } from "@/lib/components/chat/preview/previewUtils";
import { highlightCitationsInText, extractCitationTexts } from "@/lib/utils/highlightUtils";
import { getArtifactUrl } from "@/lib/utils/file";
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

    const { data: artifactData, isLoading, error: fetchError } = useArtifactContent(isOpen ? projectId : null, isOpen ? filename : null);

    // For PDFs, prioritize filename extension over mimeType since backend may return
    // application/json wrapper which would incorrectly trigger JSON renderer
    const renderType = (() => {
        const lowerFilename = filename.toLowerCase();
        if (lowerFilename.endsWith(".pdf")) return "pdf";
        return getRenderType(filename, artifactData?.mimeType);
    })();

    // Use "latest" version to get actual file content (using unified getArtifactUrl helper)
    const fileUrl = useMemo(() => {
        if (!projectId) return null;
        return getArtifactUrl({ filename, projectId, version: "latest" });
    }, [filename, projectId]);

    const highlightTexts = extractCitationTexts(citations);

    // Extract citation_map entries for precise character-position highlighting
    const citationMaps = useMemo((): CitationMapEntry[] => {
        return citations.flatMap(c => (c.metadata?.citation_map as CitationMapEntry[]) || []);
    }, [citations]);

    const processedContent = useMemo(() => {
        if (!artifactData?.content || !renderType) return "";
        if (renderType === "pdf") return "";

        // For binary formats (docx, pptx), the OfficeDocumentRenderer expects base64-encoded content
        if (["docx", "pptx"].includes(renderType)) {
            return artifactData.content;
        }

        let decodedContent: string;
        try {
            decodedContent = decodeBase64Content(artifactData.content);
        } catch {
            return artifactData.content;
        }

        if (["text", "markdown"].includes(renderType)) {
            const highlighted = highlightCitationsInText(decodedContent, citations);
            // Sanitize to prevent XSS while allowing <mark> tags for highlights
            return DOMPurify.sanitize(highlighted, { ALLOWED_TAGS: ["mark"], ALLOWED_ATTR: ["class"] });
        }

        return decodedContent;
    }, [artifactData?.content, renderType, citations]);

    const error = fetchError || renderError;

    return (
        <Dialog open={isOpen} onOpenChange={open => !open && onClose()}>
            <DialogContent className="flex h-[80vh] min-w-[60vw] flex-col">
                <DialogHeader className="flex-none border-b pb-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <FileIcon filename={filename} variant="compact" />
                            <div className="flex flex-col gap-0.5">
                                <DialogTitle className="text-base font-semibold">Source {sourceIndex + 1}</DialogTitle>
                                <DialogDescription className="text-muted-foreground flex items-center gap-1.5 text-sm">{pageLabel}</DialogDescription>
                            </div>
                        </div>
                    </div>
                </DialogHeader>

                <div className="relative flex-1 overflow-hidden">
                    {isLoading && <EmptyState variant="loading" title="Loading document..." />}

                    {error && <EmptyState variant="error" title={error instanceof Error ? error.message : String(error)} />}

                    {!isLoading && !error && renderType && (
                        <div className="h-full overflow-auto">
                            {renderType === "pdf" ? (
                                fileUrl ? (
                                    <ContentRenderer
                                        content=""
                                        rendererType={renderType}
                                        mime_type={artifactData?.mimeType}
                                        url={fileUrl}
                                        filename={filename}
                                        setRenderError={setRenderError}
                                        initialPage={pageNumber}
                                        highlightTexts={highlightTexts}
                                        citationMaps={citationMaps}
                                    />
                                ) : (
                                    <MessageBanner variant="warning" message="Unable to preview PDF: No active project context" />
                                )
                            ) : renderType === "text" || renderType === "markdown" ? (
                                <div className="p-4">
                                    <pre className="whitespace-pre-wrap select-text focus-visible:outline-none" style={{ overflowWrap: "anywhere" }} dangerouslySetInnerHTML={{ __html: processedContent }} />
                                </div>
                            ) : (
                                <ContentRenderer content={processedContent} rendererType={renderType} mime_type={artifactData?.mimeType} setRenderError={setRenderError} highlightTexts={highlightTexts} />
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
