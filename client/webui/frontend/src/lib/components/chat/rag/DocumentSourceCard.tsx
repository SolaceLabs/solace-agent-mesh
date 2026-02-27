import React, { useState } from "react";
import { ChevronRight } from "lucide-react";

import { AccordionItem, AccordionTrigger, AccordionContent } from "@/lib/components/ui/accordion";
import { FileIcon } from "@/lib/components/chat/file/FileIcon";
import type { GroupedDocument, LocationCitation } from "@/lib/utils/documentSourceUtils";

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
                        <div className="pt-4">
                            {locations.map(location => (
                                <LocationCitationItem key={location.sortKey} locationLabel={location.locationLabel} citationCount={location.citationCount} onView={() => setSelectedLocation(location)} />
                            ))}
                        </div>
                    </AccordionContent>
                </AccordionItem>
            </div>

            <CitationPreviewModal
                isOpen={!!selectedLocation}
                onClose={() => setSelectedLocation(null)}
                filename={filename}
                locationLabel={selectedLocation?.locationLabel ?? ""}
                initialLocation={selectedLocation?.sortKey ?? 1}
                sourceIndex={sourceIndex}
                fileExtension={fileExtension}
                citations={selectedLocation?.citations ?? []}
            />
        </>
    );
};
