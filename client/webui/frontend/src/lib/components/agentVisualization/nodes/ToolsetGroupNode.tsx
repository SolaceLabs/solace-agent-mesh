import type { FC } from "react";
import { Package } from "lucide-react";
import { NODE_BASE_STYLES, NODE_SELECTED_CLASS } from "../../workflowVisualization/utils/types";
import type { AgentNodeProps } from "../utils/types";

/**
 * ToolsetGroupNode - Represents a builtin tool group in the agent diagram.
 * Shows the group name with a package icon and "Group" badge.
 */
const ToolsetGroupNode: FC<AgentNodeProps> = ({ node, isSelected, onClick }) => {
    const name = node.data.label;

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
                <Package className="h-4 w-4 flex-shrink-0 text-(--color-accent-n0-wMain)" />
                <span className="truncate text-sm">{name}</span>
            </div>
            <span className="text-secondary-foreground ml-2 flex-shrink-0 rounded px-1.5 py-0.5 text-xs">Group</span>
        </div>
    );
};

export default ToolsetGroupNode;
