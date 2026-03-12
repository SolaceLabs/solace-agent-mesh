import type { FC } from "react";
import { Bot } from "lucide-react";
import { NODE_BASE_STYLES, NODE_SELECTED_CLASS } from "../../workflowVisualization/utils/types";
import type { AgentNodeProps } from "../utils/types";

/**
 * AgentHeaderNode - The top-level agent box in the agent diagram.
 * Larger than workflow agent nodes, showing name and description.
 */
const AgentHeaderNode: FC<AgentNodeProps> = ({ node, isSelected, onClick }) => {
    const name = node.data.agentName || node.data.label;
    const description = node.data.description;

    return (
        <div
            className={`${NODE_BASE_STYLES.RECTANGULAR} flex-col !items-start gap-1 ${isSelected ? NODE_SELECTED_CLASS : ""}`}
            style={{
                width: `${node.width}px`,
                height: `${node.height}px`,
            }}
            onClick={e => {
                e.stopPropagation();
                onClick?.(node);
            }}
        >
            <div className="flex w-full items-center gap-2">
                <Bot className="h-5 w-5 flex-shrink-0 text-(--color-brand-wMain)" />
                <span className="truncate text-sm font-semibold">{name}</span>
                <span className="text-secondary-foreground ml-auto flex-shrink-0 rounded px-2 py-0.5 text-xs font-medium">Agent</span>
            </div>
            {description && <div className="w-full truncate pl-7 text-xs text-(--color-secondary-text-wMain)">{description}</div>}
        </div>
    );
};

export default AgentHeaderNode;
