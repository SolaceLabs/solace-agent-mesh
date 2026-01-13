import React from "react";
import { Workflow, ExternalLink } from "lucide-react";
import { useNavigate } from "react-router-dom";
import type { NodeProps } from "../utils/types";

/**
 * Workflow reference node - Rectangle with workflow icon, name, and "Workflow" badge
 * Clicking navigates to the referenced workflow's visualization
 */
const WorkflowRefNode: React.FC<NodeProps> = ({ node, isSelected, onClick }) => {
    const navigate = useNavigate();
    const workflowName = node.data.workflowName || node.data.agentName || node.data.label;

    const handleClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        onClick?.(node);
    };

    const handleNavigate = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (workflowName) {
            navigate(`/agents/workflows/${encodeURIComponent(workflowName)}`);
        }
    };

    return (
        <div
            className={`group relative flex cursor-pointer items-center justify-between rounded-lg border-2 border-purple-600 bg-white px-4 py-3 shadow-sm transition-all duration-200 ease-in-out hover:shadow-md dark:border-purple-500 dark:bg-gray-800 ${
                isSelected ? "ring-2 ring-purple-500 ring-offset-2 dark:ring-offset-gray-900" : ""
            }`}
            style={{
                width: `${node.width}px`,
                height: `${node.height}px`,
            }}
            onClick={handleClick}
        >
            <div className="flex items-center gap-2 overflow-hidden">
                <Workflow className="h-5 w-5 flex-shrink-0 text-purple-600 dark:text-purple-400" />
                <span className="truncate text-sm font-medium text-gray-800 dark:text-gray-200">{workflowName}</span>
            </div>
            <div className="ml-2 flex flex-shrink-0 items-center gap-1">
                <span className="rounded bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700 dark:bg-purple-900/50 dark:text-purple-300">
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
            {/* Node ID badge - fades in fast (150ms), fades out slow (3s ease-in) */}
            <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 rounded bg-gray-700 px-2 py-0.5 font-mono text-xs text-gray-100 opacity-0 transition-opacity duration-[1500ms] ease-in group-hover:opacity-100 group-hover:duration-150 group-hover:ease-out dark:bg-gray-600">
                {node.id}
            </div>
        </div>
    );
};

export default WorkflowRefNode;
