import React, { useMemo } from "react";

import { MarkdownWrapper } from "@/lib/components";
import type { BaseRendererProps } from ".";
import { useCopy } from "../../../../hooks/useCopy";
import { getThemeHtmlStyles } from "@/lib/utils/themeHtmlStyles";
import type { RAGSearchResult } from "@/lib/types";
import { parseCitations } from "@/lib/utils/citations";
import { TextWithCitations } from "@/lib/components/chat/Citation";
import { useCitationClick } from "@/lib/hooks";

interface MarkdownRendererProps extends BaseRendererProps {
    ragData?: RAGSearchResult;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, ragData, isStreaming }) => {
    const { ref, handleKeyDown } = useCopy<HTMLDivElement>();
    const citations = useMemo(() => parseCitations(content, ragData), [content, ragData]);
    const handleCitationClick = useCitationClick(ragData?.taskId);

    return (
        <div className="w-full p-4">
            <div ref={ref} className="max-w-full overflow-hidden select-text focus-visible:outline-none" tabIndex={0} onKeyDown={handleKeyDown}>
                {isStreaming ? (
                    <MarkdownWrapper content={content} isStreaming={isStreaming} className="max-w-full break-words" />
                ) : (
                    <div className={getThemeHtmlStyles("max-w-full break-words")}>
                        <TextWithCitations text={content} citations={citations} onCitationClick={handleCitationClick} />
                    </div>
                )}
            </div>
        </div>
    );
};
