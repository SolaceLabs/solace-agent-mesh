import React, { useMemo } from "react";

import { MarkdownWrapper } from "@/lib/components";
import type { BaseRendererProps } from ".";
import { useCopy } from "../../../../hooks/useCopy";
import { getThemeHtmlStyles } from "@/lib/utils/themeHtmlStyles";
import type { RAGSearchResult } from "@/lib/types";
import { parseCitations } from "@/lib/utils/citations";
import { TextWithCitations } from "@/lib/components/chat/Citation";

interface MarkdownRendererProps extends BaseRendererProps {
    ragData?: RAGSearchResult;
}

/**
 * MarkdownRenderer - Renders markdown content with citation support
 *
 * Uses MarkdownWrapper for streaming content (smooth text animation)
 * Uses TextWithCitations for non-streaming content (citation support)
 */
export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, ragData, isStreaming }) => {
    const { ref, handleKeyDown } = useCopy<HTMLDivElement>();

    // Parse citations from content using ragData
    const citations = useMemo(() => {
        return parseCitations(content, ragData);
    }, [content, ragData]);

    return (
        <div className="w-full p-4">
            <div ref={ref} className="max-w-full overflow-hidden select-text focus-visible:outline-none" tabIndex={0} onKeyDown={handleKeyDown}>
                {isStreaming ? (
                    <MarkdownWrapper content={content} isStreaming={isStreaming} className="max-w-full break-words" />
                ) : (
                    <div className={getThemeHtmlStyles("max-w-full break-words")}>
                        <TextWithCitations text={content} citations={citations} />
                    </div>
                )}
            </div>
        </div>
    );
};
