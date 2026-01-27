import type { FC, MouseEvent } from "react";
import { Workflow, ExternalLink } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { NODE_BASE_STYLES, NODE_HIGHLIGHT_CLASSES, NODE_SELECTED_CLASS, type NodeProps } from "../utils/types";
import { buildWorkflowNavigationUrl } from "../WorkflowVisualizationPage";

/**
 * Workflow reference node - Rectangle with workflow icon, name, and "Workflow" badge
 * Clicking navigates to the referenced workflow's visualization
 * Supports highlighting when referenced in expressions
 */
const WorkflowRefNode: FC<NodeProps> = ({
    node,
    isSelected,
    isHighlighted,
    onClick,
    currentWorkflowName,
    parentPath = [],
}) => {
    const navigate = useNavigate();
    const workflowName = node.data.workflowName || node.data.agentName || node.data.label;

    const handleClick = (e: MouseEvent) => {
        e.stopPropagation();
        onClick?.(node);
    };

    const handleNavigate = (e: MouseEvent) => {
        e.stopPropagation();
        if (workflowName) {
            // Build new parent path: current workflow becomes closest parent
            const newParentPath = currentWorkflowName
                ? [currentWorkflowName, ...parentPath]
                : parentPath;
            navigate(buildWorkflowNavigationUrl(workflowName, newParentPath));
        }
    };

    return (
        <div
            className={`${NODE_BASE_STYLES.RECTANGULAR} ${
                isSelected ? NODE_SELECTED_CLASS : ""
            } ${isHighlighted ? NODE_HIGHLIGHT_CLASSES : ""}`}
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
            <div className="ml-2 flex flex-shrink-0 items-center gap-1">
                <span className="ml-2 flex-shrink-0 rounded px-2 py-0.5 text-sm font-medium text-[var(--color-secondary-text-wMain)]">
                    Workflow
                </span>
                <button
                    onClick={handleNavigate}
                    className="rounded p-1 text-purple-500 opacity-0 transition-opacity hover:bg-purple-100 group-hover:opacity-100 dark:text-purple-400 dark:hover:bg-purple-900/50"
                    title="Open workflow"
                >
                    <ExternalLink className="h-3.5 w-3.5" />
                </button>
            </div>
        </div>
    );
};

export default WorkflowRefNode;
