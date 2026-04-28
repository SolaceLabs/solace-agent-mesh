import React from "react";
import { MarkdownHTMLConverter } from "./MarkdownHTMLConverter";
import { StreamingMarkdown } from "./StreamingMarkdown";
import { TextWithCitations } from "@/lib/components/chat/Citation";
import type { Citation } from "@/lib/utils/citations";

interface MarkdownWrapperProps {
    content: string;
    isStreaming?: boolean;
    className?: string;
    citations?: Citation[];
    onCitationClick?: (citation: Citation) => void;
}

/**
 * A wrapper component that automatically chooses between StreamingMarkdown
 * (for smooth animated rendering during streaming) and MarkdownHTMLConverter
 * (for static content). When citations are provided, citation markers are
 * rendered as bubbles inline — both during and after streaming.
 */
const MarkdownWrapper: React.FC<MarkdownWrapperProps> = ({ content, isStreaming, className, citations, onCitationClick }) => {
    if (isStreaming) {
        return <StreamingMarkdown content={content} className={className} citations={citations} onCitationClick={onCitationClick} />;
    }

    if (citations && citations.length > 0) {
        return <TextWithCitations text={content} citations={citations} onCitationClick={onCitationClick} />;
    }

    return <MarkdownHTMLConverter className={className}>{content}</MarkdownHTMLConverter>;
};

export { MarkdownWrapper };
