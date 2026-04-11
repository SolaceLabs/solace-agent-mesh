import type { FC } from "react";
import { Wrench } from "lucide-react";
import { NODE_BASE_STYLES, NODE_SELECTED_CLASS } from "../../workflowVisualization/utils/types";
import type { AgentNodeProps } from "../utils/types";

/**
 * ToolNode - Represents an individual tool in the agent diagram.
 * Shows tool name with a type badge (builtin, remote, mcp).
 */
const ToolNode: FC<AgentNodeProps> = ({ node, isSelected, onClick }) => {
    const name = node.data.toolName || node.data.label;
    const toolType = node.data.toolType;

    const typeBadge = toolType ? formatToolType(toolType) : null;

    return (
        <div
            className={`${NODE_BASE_STYLES.RECTANGULAR} ${isSelected ? NODE_SELECTED_CLASS : ""}`}
            style={{
                width: `${node.width}px`,
                height: `${node.height}px`,
            }}
            onClick={onClick ? e => { e.stopPropagation(); onClick(node); } : undefined}
        >
            <div className="flex items-center gap-2 overflow-hidden">
                <Wrench className="h-4 w-4 flex-shrink-0 text-(--color-accent-n0-wMain)" />
                <span className="truncate text-sm">{name}</span>
            </div>
            {typeBadge && <span className="text-secondary-foreground ml-2 flex-shrink-0 rounded px-1.5 py-0.5 text-xs">{typeBadge}</span>}
        </div>
    );
};

function formatToolType(type: string): string {
    switch (type) {
        case "sam_remote":
            return "remote";
        case "builtin":
            return "builtin";
        case "mcp":
            return "MCP";
        default:
            return type;
    }
}

export default ToolNode;
