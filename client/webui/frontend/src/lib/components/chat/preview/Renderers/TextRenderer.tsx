import type { BaseRendererProps } from ".";
import { useCopy } from "../../../../hooks/useCopy";

interface TextRendererProps extends BaseRendererProps {
    className?: string;
}

export const TextRenderer: React.FC<TextRendererProps> = ({ content, className = "" }) => {
    const { ref, handleKeyDown } = useCopy<HTMLPreElement>();

    return (
        <div className={`overflow-auto p-4 ${className}`}>
            <pre ref={ref} className="whitespace-pre-wrap select-text focus-visible:outline-none" style={{ overflowWrap: "anywhere" }} tabIndex={0} onKeyDown={handleKeyDown}>
                {content}
            </pre>
        </div>
    );
};
