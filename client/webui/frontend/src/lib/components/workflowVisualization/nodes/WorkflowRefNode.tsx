import type { MouseEvent } from "react";
import { Workflow } from "lucide-react";
import { NODE_BASE_STYLES, NODE_HIGHLIGHT_CLASSES, NODE_SELECTED_CLASS, type NodeProps } from "../utils/types";

/**
 * Workflow reference node - Rectangle with workflow icon, name, and "Workflow" badge
 * Clicking navigates to the referenced workflow's visualization
 * Supports highlighting when referenced in expressions
 */
const WorkflowRefNode: React.FC<NodeProps> = ({ node, isSelected, isHighlighted, onClick }) => {
    const workflowName = node.data.workflowName || node.data.agentName || node.data.label;

    const handleClick = (e: MouseEvent) => {
        e.stopPropagation();
        onClick?.(node);
    };

    return (
        <div
            className={`${NODE_BASE_STYLES.RECTANGULAR} ${isSelected ? NODE_SELECTED_CLASS : ""} ${isHighlighted ? NODE_HIGHLIGHT_CLASSES : ""}`}
            style={{
                width: `${node.width}px`,
                height: `${node.height}px`,
            }}
            onClick={handleClick}
        >
            <div className="flex items-center gap-2 overflow-hidden">
                <Workflow className="h-5 w-5 flex-shrink-0 text-[var(--color-brand-wMain)]" />
                <span className="truncate text-sm font-semibold">{workflowName}</span>
            </div>
            <span className="ml-2 flex-shrink-0 rounded px-2 py-0.5 text-sm font-medium text-[var(--color-secondary-text-wMain)]">Workflow</span>
        </div>
    );
};

export default WorkflowRefNode;
