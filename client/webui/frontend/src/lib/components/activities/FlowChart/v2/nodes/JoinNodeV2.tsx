import React from "react";
import type { LayoutNode } from "../utils/types";

interface JoinNodeV2Props {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
}

const JoinNodeV2: React.FC<JoinNodeV2Props> = ({ node, isSelected, onClick }) => {
    const getStatusColor = () => {
        switch (node.data.status) {
            case "completed":
                return "bg-green-100 border-green-500 dark:bg-green-900/30 dark:border-green-500";
            case "in-progress":
                return "bg-blue-100 border-blue-500 dark:bg-blue-900/30 dark:border-blue-500";
            case "error":
                return "bg-red-100 border-red-500 dark:bg-red-900/30 dark:border-red-500";
            default:
                return "bg-gray-100 border-gray-400 dark:bg-gray-800 dark:border-gray-600";
        }
    };

    const getStrategyLabel = () => {
        const strategy = node.data.joinStrategy || 'all';
        switch (strategy) {
            case 'any':
                return 'Any';
            case 'n_of_m':
                return `${node.data.joinN}/${node.data.waitFor?.length || 0}`;
            case 'all':
            default:
                return 'All';
        }
    };

    const waitCount = node.data.waitFor?.length || 0;

    return (
        <div
            className="relative flex items-center justify-center cursor-pointer"
            style={{ width: `${node.width}px`, height: `${node.height}px` }}
            onClick={(e) => {
                e.stopPropagation();
                onClick?.(node);
            }}
            title={node.data.description || `Join: waiting for ${getStrategyLabel()} of ${waitCount} nodes`}
        >
            {/* Circle Shape for Join (synchronization point) */}
            <div
                className={`w-12 h-12 rounded-full border-2 shadow-sm transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-md flex items-center justify-center ${getStatusColor()} ${
                    isSelected ? "ring-2 ring-blue-500" : ""
                }`}
            >
                {/* Content */}
                <div className="flex flex-col items-center justify-center text-center pointer-events-none">
                    <div className="text-[10px] font-bold text-gray-800 dark:text-gray-200">
                        {node.data.label}
                    </div>
                    <div className="text-[8px] text-gray-500 dark:text-gray-400">
                        {getStrategyLabel()}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default JoinNodeV2;
