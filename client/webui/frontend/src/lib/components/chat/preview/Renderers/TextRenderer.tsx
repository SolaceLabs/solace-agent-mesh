import type { BaseRendererProps } from ".";
import { useCopy } from "../../../../hooks/useCopy";
import { StreamingMarkdown } from "@/lib/components";

interface TextRendererProps extends BaseRendererProps {
    className?: string;
}

export const TextRenderer: React.FC<TextRendererProps> = ({ content, className = "", isStreaming }) => {
    const { ref, handleKeyDown } = useCopy<HTMLPreElement>();

    if (isStreaming) {
        // Use StreamingMarkdown for smooth rendering effect, even though it might interpret markdown.
        return (
            <div className={`overflow-auto p-4 ${className}`}>
                <div ref={ref as unknown as React.RefObject<HTMLDivElement>} className="whitespace-pre-wrap select-text focus-visible:outline-none" tabIndex={0} onKeyDown={handleKeyDown}>
                    <StreamingMarkdown content={content} />
                </div>
            </div>
        );
    }

    return (
        <div className={`overflow-auto p-4 ${className}`}>
            <pre ref={ref} className="whitespace-pre-wrap select-text focus-visible:outline-none" style={{ overflowWrap: "anywhere" }} tabIndex={0} onKeyDown={handleKeyDown}>
                {content}
            </pre>
        </div>
    );
};
