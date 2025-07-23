import React from "react";

import { MarkdownHTMLConverter } from "@/lib/components";
import type { BaseRendererProps } from ".";

export const MarkdownRenderer: React.FC<BaseRendererProps> = ({ content }) => {
    return (
        <div className="w-full">
            <div className="max-w-full overflow-hidden">
                <MarkdownHTMLConverter className="max-w-full break-words">
                    {content}
                </MarkdownHTMLConverter>
            </div>
        </div>
    );
};
