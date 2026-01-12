import React from "react";
import type { NodeProps } from "../utils/types";

/**
 * Condition pill node - Small pill showing a switch case condition
 * Positioned above the target node with curved edge from switch and straight edge to target
 */
const ConditionPillNode: React.FC<NodeProps> = ({ node, isSelected, onClick }) => {
    const isDefault = node.data.isDefaultCase;
    const label = node.data.conditionLabel || node.data.label;

    return (
        <div
            className={`flex cursor-pointer items-center justify-center rounded-full border px-2 py-1 text-xs font-medium shadow-sm transition-all duration-200 ${
                isDefault
                    ? "border-amber-400 bg-amber-50 text-amber-700 dark:border-amber-500 dark:bg-amber-900/30 dark:text-amber-300"
                    : "border-purple-400 bg-purple-50 text-purple-700 dark:border-purple-500 dark:bg-purple-900/30 dark:text-purple-300"
            } ${isSelected ? "ring-2 ring-blue-500 ring-offset-1 dark:ring-offset-gray-900" : ""}`}
            style={{
                width: `${node.width}px`,
                height: `${node.height}px`,
            }}
            onClick={e => {
                e.stopPropagation();
                onClick?.(node);
            }}
            title={label}
        >
            <span className="block w-full overflow-hidden text-ellipsis whitespace-nowrap text-center">{label}</span>
        </div>
    );
};

export default ConditionPillNode;
