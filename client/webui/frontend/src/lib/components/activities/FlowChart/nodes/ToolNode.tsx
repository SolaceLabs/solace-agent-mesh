import React from "react";
import { Wrench } from "lucide-react";
import type { LayoutNode } from "../utils/types";

interface ToolNodeProps {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
}

const ToolNode: React.FC<ToolNodeProps> = ({ node, isSelected, onClick }) => {
    const isProcessing = node.data.status === "in-progress";
    const haloClass = isProcessing ? 'processing-halo' : '';

    return (
        <div
            className={`cursor-pointer rounded-lg border-2 border-cyan-600 bg-white px-3 py-2 text-gray-800 shadow-md transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-xl dark:border-cyan-400 dark:bg-gray-800 dark:text-gray-200 ${
                isSelected ? "ring-2 ring-blue-500" : ""
            } ${haloClass}`}
            onClick={(e) => {
                e.stopPropagation();
                onClick?.(node);
            }}
            title={node.data.description}
        >
            <div className="flex items-center justify-center gap-2">
                <Wrench className="h-3.5 w-3.5 flex-shrink-0 text-cyan-600 dark:text-cyan-400" />
                <div className="text-sm truncate">{node.data.label}</div>
            </div>
        </div>
    );
};

export default ToolNode;
