import React from "react";
import { Bot } from "lucide-react";
import { NODE_BASE_STYLES, NODE_HIGHLIGHT_CLASSES, NODE_SELECTED_CLASS, type NodeProps } from "../utils/types";

/**
 * Agent node - Rectangle with robot icon, agent name, and "Agent" badge
 * Supports highlighting when referenced in expressions (shown with amber glow)
 */
const AgentNode: React.FC<NodeProps> = ({ node, isSelected, isHighlighted, onClick }) => {
    const agentName = node.data.agentName || node.data.label;

    return (
        <div
            className={`${NODE_BASE_STYLES.RECTANGULAR} ${
                isSelected ? NODE_SELECTED_CLASS : ""
            } ${isHighlighted ? NODE_HIGHLIGHT_CLASSES : ""}`}
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
        </div>
    );
};

export default AgentNode;
