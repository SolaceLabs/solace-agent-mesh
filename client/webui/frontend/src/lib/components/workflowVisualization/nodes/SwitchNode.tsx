import React from "react";
import { GitBranch } from "lucide-react";
import type { NodeProps } from "../utils/types";

/**
 * Switch node - Shows conditional branching
 * Conditions are displayed in separate pill nodes above each branch
 */
const SwitchNode: React.FC<NodeProps> = ({ node, isSelected, onClick }) => {
    const cases = node.data.cases || [];
    const hasDefault = !!node.data.defaultCase;
    const totalCases = cases.length + (hasDefault ? 1 : 0);

    return (
        <div
            className={`flex cursor-pointer items-center justify-between rounded-lg border-2 border-purple-500 bg-white px-3 py-2 shadow-sm transition-all duration-200 hover:shadow-md dark:border-purple-400 dark:bg-gray-800 ${
                isSelected ? "ring-2 ring-purple-500 ring-offset-2 dark:ring-offset-gray-900" : ""
            }`}
            style={{
                width: `${node.width}px`,
            }}
            onClick={e => {
                e.stopPropagation();
                onClick?.(node);
            }}
        >
            <div className="flex items-center gap-2">
                <GitBranch className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                <span className="text-sm font-medium text-purple-900 dark:text-purple-100">{node.data.label}</span>
            </div>
            <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 dark:text-gray-400">{totalCases} cases</span>
                <span className="rounded bg-purple-100 px-1.5 py-0.5 text-xs font-medium text-purple-700 dark:bg-purple-800/50 dark:text-purple-300">
                    Switch
                </span>
            </div>
        </div>
    );
};

export default SwitchNode;
