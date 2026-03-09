import React, { useState, useMemo } from "react";
import { ChevronRight, Loader2 } from "lucide-react";

import { AccordionItem, AccordionTrigger, AccordionContent } from "@/lib/components/ui/accordion";
import { FileIcon } from "@/lib/components/chat/file/FileIcon";
import { useSessionArtifactContent } from "@/lib/api/artifacts";
import { useChatContext } from "@/lib/hooks";
import { canPreviewArtifact } from "@/lib/components/chat/preview/previewUtils";
import { ArtifactPreviewDownload } from "@/lib/components/chat/artifact/ArtifactPreviewDownload";
import type { GroupedDocument, LocationCitation } from "@/lib/utils/documentSourceUtils";
import type { ArtifactInfo } from "@/lib/types";

import { CitationPreviewModal } from "./CitationPreviewModal";
import { LocationCitationItem } from "./PageCitationItem";

export interface DocumentSourceCardProps {
    document: GroupedDocument;
    sourceIndex: number;
}

/**
 * Collapsible card for a single document using Accordion
 * Shows document info in trigger, locations list in content
 */
export const DocumentSourceCard: React.FC<DocumentSourceCardProps> = ({ document, sourceIndex }) => {
    const { totalCitations, locations, fileExtension, filename } = document;
    const [selectedLocation, setSelectedLocation] = useState<LocationCitation | null>(null);

    const { sessionId } = useChatContext();

    const needsPreviewCheck = fileExtension.toLowerCase() === "pptx" || fileExtension.toLowerCase() === "docx";

    // Extract file version from the first citation across all locations
    const fileVersion: number | undefined = locations[0]?.citations[0]?.metadata?.file_version ?? undefined;

    // Fetch artifact content to check if it can be previewed
    const { data: artifactData, isLoading: isLoadingArtifact, error: artifactError } = useSessionArtifactContent(needsPreviewCheck ? sessionId : null, needsPreviewCheck ? filename : null, fileVersion);

    // Check if artifact can be previewed (based on size and file type support)
    const previewCheck = useMemo(() => {
        if (!needsPreviewCheck) {
            return { canPreview: true };
        }

        if (artifactError) {
            return { canPreview: false, reason: "Unable to check preview availability" };
        }

        if (!artifactData) {
            return null;
        }

        // Create a minimal ArtifactInfo object for the preview check
        // Calculate size from base64 content if available (rough estimate: base64 length * 0.75)
        const estimatedSize = artifactData.content ? Math.floor(artifactData.content.length * 0.75) : 0;

        const mockArtifact: ArtifactInfo = {
            filename,
            mime_type: artifactData.mimeType,
            size: estimatedSize,
            last_modified: "",
        };

        return canPreviewArtifact(mockArtifact);
    }, [artifactData, artifactError, filename, needsPreviewCheck]);

    return (
        <>
            <div className="dark:bg-muted/50 border-border overflow-hidden rounded-[4px] border bg-white">
                <AccordionItem value={`document-${sourceIndex}`} className="border-none">
                    <AccordionTrigger className="items-center gap-2 p-4 hover:no-underline [&>svg:last-child]:hidden [&[data-state=open]>svg:first-child]:rotate-90">
                        <ChevronRight className="text-primary h-4 w-4 shrink-0 self-center transition-transform duration-200" />

                        <FileIcon filename={filename} variant="compact" />

                        <div className="flex min-w-0 flex-1 flex-col items-start gap-0.5">
                            <span className="text-foreground truncate text-sm font-medium">{filename}</span>
                            <span className="text-muted-foreground truncate text-sm">
                                {fileExtension.toUpperCase()} file | {totalCitations} citation
                                {totalCitations !== 1 ? "s" : ""}
                            </span>
                        </div>
                    </AccordionTrigger>
                    <AccordionContent className="border-border border-t px-4 pb-3">
                        {isLoadingArtifact || !previewCheck ? (
                            <div className="text-muted-foreground flex items-center justify-center py-8">
                                <Loader2 className="h-5 w-5 animate-spin" />
                            </div>
                        ) : !previewCheck.canPreview ? (
                            <div className="py-4">
                                <ArtifactPreviewDownload
                                    artifact={
                                        {
                                            filename,
                                            mime_type: artifactData?.mimeType || "",
                                            size: artifactData?.content ? Math.floor(artifactData.content.length * 0.75) : 0,
                                            last_modified: "",
                                        } as ArtifactInfo
                                    }
                                    message={previewCheck.reason || "Preview not available"}
                                />
                            </div>
                        ) : (
                            <div className="pt-4">
                                {locations.map(location => (
                                    <LocationCitationItem key={location.sortKey} locationLabel={location.locationLabel} citationCount={location.citationCount} onView={() => setSelectedLocation(location)} />
                                ))}
                            </div>
                        )}
                    </AccordionContent>
                </AccordionItem>
            </div>

            <CitationPreviewModal
                isOpen={!!selectedLocation}
                onClose={() => setSelectedLocation(null)}
                filename={filename}
                locationLabel={selectedLocation?.locationLabel ?? ""}
                initialLocation={selectedLocation?.sortKey ?? 1}
                fileExtension={fileExtension}
                citations={selectedLocation?.citations ?? []}
            />
        </>
    );
};
