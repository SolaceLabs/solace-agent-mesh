import type { FC, MouseEvent } from "react";
import { Workflow, ExternalLink } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { NODE_HIGHLIGHT_CLASSES, NODE_SELECTED_CLASSES, type NodeProps } from "../utils/types";
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
            className={`group relative flex cursor-pointer items-center justify-between rounded-lg border-2 border-(--color-accent-n3-wMain) bg-(--color-background-w10) px-4 py-3 shadow-sm transition-all duration-200 ease-in-out hover:shadow-md dark:border-(--color-accent-n3-w30) dark:bg-(--color-background-wMain) ${
                isSelected ? NODE_SELECTED_CLASSES.PURPLE : ""
            } ${isHighlighted ? NODE_HIGHLIGHT_CLASSES : ""}`}
            style={{
                width: `${node.width}px`,
                height: `${node.height}px`,
            }}
            onClick={handleClick}
        >
            <div className="flex items-center gap-2 overflow-hidden">
                <Workflow className="h-5 w-5 flex-shrink-0 text-(--color-accent-n3-wMain) dark:text-(--color-accent-n3-w30)" />
                <span className="truncate text-sm font-medium text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10)">{workflowName}</span>
            </div>
            <div className="ml-2 flex flex-shrink-0 items-center gap-1">
                <span className="rounded bg-(--color-accent-n3-w10) px-2 py-0.5 text-xs font-medium text-(--color-accent-n3-w100) dark:bg-(--color-accent-n3-w100)/50 dark:text-(--color-accent-n3-w30)">
                    Workflow
                </span>
                <button
                    onClick={handleNavigate}
                    className="rounded p-1 text-(--color-accent-n3-wMain) opacity-0 transition-opacity hover:bg-(--color-accent-n3-w10) group-hover:opacity-100 dark:text-(--color-accent-n3-w30) dark:hover:bg-(--color-accent-n3-w100)/50"
                    title="Open workflow"
                >
                    <ExternalLink className="h-3.5 w-3.5" />
                </button>
            </div>
        </div>
    );
};

export default WorkflowRefNode;
