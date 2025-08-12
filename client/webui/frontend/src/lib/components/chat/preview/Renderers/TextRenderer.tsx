import type { BaseRendererProps } from ".";
import { useCopy } from "../../../../hooks/useCopy";

interface TextRendererProps extends BaseRendererProps {
    className?: string;
}

export const TextRenderer: React.FC<TextRendererProps> = ({ content, className = "" }) => {
	const { ref, handleKeyDown } = useCopy<HTMLPreElement>();
	
	return (
		<div className={`p-4 overflow-auto ${className}`}>
			<pre 
				ref={ref}
				className="whitespace-pre-wrap focus-visible:outline-none select-text" 
				style={{ overflowWrap: "anywhere" }}
				tabIndex={0}
				onKeyDown={handleKeyDown}
			>
				{content}
			</pre>
		</div>
	);
}
