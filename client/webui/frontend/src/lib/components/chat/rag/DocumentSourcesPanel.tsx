import React, { useMemo, useEffect, useState } from "react";
import { Link2, Search } from "lucide-react";

import { Accordion } from "@/lib/components/ui/accordion";
import { EmptyState } from "@/lib/components/common/EmptyState";
import { useChatContext } from "@/lib/hooks";
import type { RAGSearchResult } from "@/lib/types";
import { groupDocumentSources } from "@/lib/utils/documentSourceUtils";

import { DocumentSourceCard } from "./DocumentSourceCard";

export interface DocumentSourcesPanelProps {
    ragData: RAGSearchResult[] | null;
    enabled: boolean;
}

/**
 * Main panel component for displaying document sources
 * Groups documents by filename and shows pages with citation counts
 */
export const DocumentSourcesPanel: React.FC<DocumentSourcesPanelProps> = ({ ragData, enabled }) => {
    const { expandedDocumentFilename, setExpandedDocumentFilename } = useChatContext();
    const [expandedValues, setExpandedValues] = useState<string[]>([]);

    // Group document sources by filename and page
    const groupedDocuments = useMemo(() => {
        if (!ragData || ragData.length === 0) return [];
        return groupDocumentSources(ragData);
    }, [ragData]);

    // Auto-expand document when expandedDocumentFilename is set from citation click
    useEffect(() => {
        if (!expandedDocumentFilename) return;

        // Find the index of the document to expand
        const idx = groupedDocuments.findIndex(doc => doc.filename === expandedDocumentFilename);
        if (idx >= 0) {
            // Add to expanded values without closing others
            setExpandedValues(prev => {
                const value = `document-${idx}`;
                if (prev.includes(value)) return prev;
                return [...prev, value];
            });
        }

        // Clear the auto-expand state after applying it
        const timer = setTimeout(() => setExpandedDocumentFilename(null), 100);
        return () => clearTimeout(timer);
    }, [expandedDocumentFilename, groupedDocuments, setExpandedDocumentFilename]);

    // Disabled state
    if (!enabled) {
        return <EmptyState title="Document Sources" subtitle="Source visibility is disabled in settings" variant="noImage" image={<Link2 className="h-12 w-12 opacity-50" />} />;
    }

    // Empty state
    if (!ragData || ragData.length === 0 || groupedDocuments.length === 0) {
        return (
            <EmptyState
                title="Document Sources"
                subtitle={
                    <>
                        <span>No document sources available yet</span>
                        <br />
                        <span className="text-xs">Document citations will appear here after a document search</span>
                    </>
                }
                variant="noImage"
                image={<Search className="h-12 w-12 opacity-50" />}
            />
        );
    }

    // Calculate total citations
    const totalCitations = groupedDocuments.reduce((sum, doc) => sum + doc.totalCitations, 0);

    return (
        <div className="flex h-full flex-col overflow-hidden">
            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
                {/* Header */}
                <div className="mb-4">
                    <h3 className="text-muted-foreground text-sm font-semibold">
                        {groupedDocuments.length} Document
                        {groupedDocuments.length !== 1 ? "s" : ""} | {totalCitations} Citation{totalCitations !== 1 ? "s" : ""}
                    </h3>
                </div>

                {/* Document cards */}
                <Accordion type="multiple" value={expandedValues} onValueChange={setExpandedValues} className="space-y-2">
                    {groupedDocuments.map((document, idx) => (
                        <DocumentSourceCard key={document.filename} document={document} sourceIndex={idx} />
                    ))}
                </Accordion>
            </div>
        </div>
    );
};
