import React from "react";
import { MarkdownHTMLConverter } from "./MarkdownHTMLConverter";
import { TextWithCitations } from "@/lib/components/chat/Citation";
import { useStreamingSpeed, useStreamingAnimation } from "@/lib/hooks";
import type { Citation } from "@/lib/utils/citations";

interface StreamingMarkdownProps {
    content: string;
    className?: string;
    citations?: Citation[];
    onCitationClick?: (citation: Citation) => void;
}

const StreamingMarkdown: React.FC<StreamingMarkdownProps> = ({ content, className, citations, onCitationClick }) => {
    const { state, contentRef } = useStreamingSpeed(content);
    const displayedContent = useStreamingAnimation(state, contentRef);

    if (citations && citations.length > 0) {
        return <TextWithCitations text={displayedContent} citations={citations} onCitationClick={onCitationClick} />;
    }

    return <MarkdownHTMLConverter className={className}>{displayedContent}</MarkdownHTMLConverter>;
};

export { StreamingMarkdown };
