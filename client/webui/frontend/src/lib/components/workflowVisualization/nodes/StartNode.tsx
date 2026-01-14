import React from "react";
import { Play } from "lucide-react";
import { NODE_HIGHLIGHT_CLASSES, NODE_SELECTED_CLASSES, type NodeProps } from "../utils/types";

/**
 * Start node - Pill-shaped node marking the beginning of the workflow
 * Supports highlighting when referenced via workflow.input in expressions
 */
const StartNode: React.FC<NodeProps> = ({ node, isSelected, isHighlighted, onClick }) => {
    return (
        <div
            className={`flex cursor-pointer items-center justify-center gap-2 rounded-full border-2 border-indigo-500 bg-indigo-50 px-4 py-2 shadow-sm transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-md dark:border-indigo-400 dark:bg-indigo-900/50 ${
                isSelected ? NODE_SELECTED_CLASSES.BLUE : ""
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
            <Play className="h-4 w-4 text-indigo-600 dark:text-indigo-300" />
            <span className="text-sm font-semibold text-indigo-900 dark:text-indigo-100">{node.data.label}</span>
        </div>
    );
};

export default StartNode;
