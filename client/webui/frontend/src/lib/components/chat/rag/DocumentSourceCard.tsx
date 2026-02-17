import React from "react";
import { ChevronRight } from "lucide-react";

import { AccordionItem, AccordionTrigger, AccordionContent } from "@/lib/components/ui/accordion";
import { FileIcon } from "@/lib/components/chat/file/FileIcon";
import type { GroupedDocument } from "@/lib/utils/documentSourceUtils";

import { PageCitationItem } from "./PageCitationItem";

export interface DocumentSourceCardProps {
    document: GroupedDocument;
    sourceIndex: number;
}

/**
 * Collapsible card for a single document using Accordion
 * Shows document info in trigger, pages list in content
 * Design matches Figma: white bg, border #CFD3D9, chevron on left
 */
export const DocumentSourceCard: React.FC<DocumentSourceCardProps> = ({ document, sourceIndex }) => {
    const { totalCitations, pages, fileExtension, filename } = document;

    return (
        <div className="dark:border-border dark:bg-muted/50 overflow-hidden rounded-[4px] border border-[#CFD3D9] bg-white">
            <AccordionItem value={`document-${sourceIndex}`} className="border-none">
                {/* Hide default chevron with [&>svg:last-child]:hidden, use custom chevron on left */}
                <AccordionTrigger className="items-center gap-2 p-4 hover:no-underline [&>svg:last-child]:hidden [&[data-state=open]>svg:first-child]:rotate-90">
                    {/* Chevron on the left, centered vertically */}
                    <ChevronRight className="dark:text-primary h-4 w-4 shrink-0 self-center text-[#015B82] transition-transform duration-200" />

                    <FileIcon filename={filename} variant="compact" />

                    <div className="flex min-w-0 flex-1 flex-col items-start gap-0.5">
                        <span className="dark:text-foreground text-sm font-medium text-[#273749]">Source {sourceIndex + 1}</span>
                        <span className="dark:text-muted-foreground truncate text-sm text-[#647481]">
                            {fileExtension} file | {totalCitations} citation
                            {totalCitations !== 1 ? "s" : ""}
                        </span>
                    </div>
                </AccordionTrigger>
                <AccordionContent className="dark:border-border border-t border-[#CFD3D9] px-4 pb-3">
                    <div className="pt-4">
                        {pages.map((page, idx) => (
                            <PageCitationItem key={`page-${idx}`} pageLabel={page.pageLabel} citationCount={page.citationCount} />
                        ))}
                    </div>
                </AccordionContent>
            </AccordionItem>
        </div>
    );
};
