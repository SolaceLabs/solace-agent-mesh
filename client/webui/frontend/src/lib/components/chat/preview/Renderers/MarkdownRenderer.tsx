import React from "react";

import { MarkdownHTMLConverter } from "@/lib/components";
import type { BaseRendererProps } from ".";
import { useCopy } from "../../../../hooks/useCopy";

export const MarkdownRenderer: React.FC<BaseRendererProps> = ({ content }) => {
    const { ref, handleKeyDown } = useCopy<HTMLDivElement>();

    return (
        <div className="w-full p-4">
            <div ref={ref} className="max-w-full overflow-hidden select-text focus-visible:outline-none" tabIndex={0} onKeyDown={handleKeyDown}>
                <MarkdownHTMLConverter className="max-w-full break-words">{content}</MarkdownHTMLConverter>
            </div>
        </div>
    );
};
