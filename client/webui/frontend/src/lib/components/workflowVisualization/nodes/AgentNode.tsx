import React from "react";
import { Bot } from "lucide-react";
import type { NodeProps } from "../utils/types";

/**
 * Agent node - Rectangle with robot icon, agent name, and "Agent" badge
 */
const AgentNode: React.FC<NodeProps> = ({ node, isSelected, onClick }) => {
    const agentName = node.data.agentName || node.data.label;

    return (
        <div
            className={`group relative flex cursor-pointer items-center justify-between rounded-lg border-2 border-blue-600 bg-white px-4 py-3 shadow-sm transition-all duration-200 ease-in-out hover:shadow-md dark:border-blue-500 dark:bg-gray-800 ${
                isSelected ? "ring-2 ring-blue-500 ring-offset-2 dark:ring-offset-gray-900" : ""
            }`}
            style={{
                width: `${node.width}px`,
                height: `${node.height}px`,
            }}
            onClick={e => {
                e.stopPropagation();
                onClick?.(node);
            }}
        >
            <div className="flex items-center gap-2 overflow-hidden">
                <Bot className="h-5 w-5 flex-shrink-0 text-blue-600 dark:text-blue-400" />
                <span className="truncate text-sm font-medium text-gray-800 dark:text-gray-200">{agentName}</span>
            </div>
            <span className="ml-2 flex-shrink-0 rounded bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/50 dark:text-blue-300">
                Agent
            </span>
            {/* Node ID badge - fades in fast (150ms), fades out slow (3s ease-in) */}
            <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 rounded bg-gray-700 px-2 py-0.5 font-mono text-xs text-gray-100 opacity-0 transition-opacity duration-[1500ms] ease-in group-hover:opacity-100 group-hover:duration-150 group-hover:ease-out dark:bg-gray-600">
                {node.id}
            </div>
        </div>
    );
};

export default AgentNode;
