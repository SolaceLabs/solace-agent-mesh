import React from "react";
import { MarkdownHTMLConverter } from "./MarkdownHTMLConverter";
import { StreamingMarkdown } from "./StreamingMarkdown";

interface MarkdownWrapperProps {
    content: string;
    isStreaming?: boolean;
    className?: string;
}

/**
 * A wrapper component that automatically chooses between StreamingMarkdown
 * (for smooth animated rendering during streaming) and MarkdownHTMLConverter
 * (for static content).
 */
const MarkdownWrapper: React.FC<MarkdownWrapperProps> = ({ content, isStreaming, className }) => {
    if (isStreaming) {
        return <StreamingMarkdown content={content} className={className} />;
    }

    return <MarkdownHTMLConverter className={className}>{content}</MarkdownHTMLConverter>;
};

export { MarkdownWrapper };
