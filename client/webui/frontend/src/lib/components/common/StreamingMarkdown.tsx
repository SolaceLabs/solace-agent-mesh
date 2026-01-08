import React from "react";
import { MarkdownHTMLConverter } from "./MarkdownHTMLConverter";
import { useStreamingSpeed, useStreamingAnimation } from "@/lib/hooks";

interface StreamingMarkdownProps {
    content: string;
    className?: string;
}

const StreamingMarkdown: React.FC<StreamingMarkdownProps> = ({ content, className }) => {
    const { state, contentRef } = useStreamingSpeed(content);
    const displayedContent = useStreamingAnimation(state, contentRef);

    return <MarkdownHTMLConverter className={className}>{displayedContent}</MarkdownHTMLConverter>;
};

export { StreamingMarkdown };
