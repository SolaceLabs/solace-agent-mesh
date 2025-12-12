import React from "react";
import type { LayoutNode } from "../utils/types";

interface ConditionalNodeV2Props {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
}

const ConditionalNodeV2: React.FC<ConditionalNodeV2Props> = ({ node, isSelected, onClick }) => {
    const getStatusColor = () => {
        switch (node.data.status) {
            case "completed":
                return "bg-amber-100 border-amber-500 dark:bg-amber-900/30 dark:border-amber-500";
            case "in-progress":
                return "bg-blue-100 border-blue-500 dark:bg-blue-900/30 dark:border-blue-500";
            case "error":
                return "bg-red-100 border-red-500 dark:bg-red-900/30 dark:border-red-500";
            default:
                return "bg-gray-100 border-gray-400 dark:bg-gray-800 dark:border-gray-600";
        }
    };

    return (
        <div
            className="relative flex items-center justify-center cursor-pointer"
            style={{ width: `${node.width}px`, height: `${node.height}px` }}
            onClick={(e) => {
                e.stopPropagation();
                onClick?.(node);
            }}
            title={node.data.description}
        >
            {/* Diamond Shape using rotation */}
            <div
                className={`absolute h-12 w-12 rotate-45 border-2 shadow-sm transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-md ${getStatusColor()} ${
                    isSelected ? "ring-2 ring-blue-500" : ""
                }`}
            />

            {/* Content (unrotated) */}
            <div className="z-10 flex flex-col items-center justify-center text-center pointer-events-none px-1">
                <div className="text-[10px] font-bold text-gray-800 dark:text-gray-200 max-w-[100px] truncate">
                    {node.data.label}
                </div>
            </div>

            {/* Branch Labels */}
            {node.data.conditionResult !== undefined && (
                <>
                    <div className="absolute bottom-[-20px] left-1/2 transform -translate-x-1/2 text-[10px] font-bold text-gray-600 dark:text-gray-300 bg-white/80 dark:bg-gray-900/80 px-1 rounded">
                        {node.data.conditionResult ? "True" : "False"}
                    </div>
                    <div className="absolute right-[-20px] top-1/2 transform -translate-y-1/2 text-[10px] font-bold text-gray-600 dark:text-gray-300 bg-white/80 dark:bg-gray-900/80 px-1 rounded">
                        {node.data.conditionResult ? "False" : "True"}
                    </div>
                </>
            )}
        </div>
    );
};

export default ConditionalNodeV2;
