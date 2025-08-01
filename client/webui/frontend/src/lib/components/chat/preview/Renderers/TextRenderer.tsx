import type { BaseRendererProps } from ".";

interface TextRendererProps extends BaseRendererProps {
    className?: string;
}

export const TextRenderer: React.FC<TextRendererProps> = ({ content, className = "" }) => {
	return (
		<div className={`p-4 overflow-auto ${className}`}>
			<pre className="whitespace-pre-wrap focus-visible:outline-none" style={{ overflowWrap: "anywhere" }} contentEditable="true">
				{content}
			</pre>
		</div>
	);
}
