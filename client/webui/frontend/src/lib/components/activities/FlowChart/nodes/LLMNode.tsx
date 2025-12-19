import React from "react";
import type { LayoutNode } from "../utils/types";

interface LLMNodeProps {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
}

const LLMNode: React.FC<LLMNodeProps> = ({ node, isSelected, onClick }) => {
    const isProcessing = node.data.status === "in-progress";
    const haloClass = isProcessing ? 'processing-halo' : '';

    return (
        <div
            className={`relative overflow-hidden cursor-pointer rounded-full border-2 border-teal-600 bg-white px-3 py-1 text-gray-800 shadow-md transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-xl dark:border-teal-400 dark:bg-gray-800 dark:text-gray-200 ${
                isSelected ? "ring-2 ring-blue-500" : ""
            } ${haloClass}`}
            style={{
                textAlign: "center",
            }}
            onClick={(e) => {
                e.stopPropagation();
                onClick?.(node);
            }}
            title={node.data.description}
        >
            <div className="text-sm">
                {node.data.label}
            </div>
        </div>
    );
};

export default LLMNode;
