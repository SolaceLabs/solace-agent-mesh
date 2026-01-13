import React from "react";
import { GitBranch } from "lucide-react";
import { NODE_HIGHLIGHT_CLASSES, NODE_ID_BADGE_CLASSES, NODE_SELECTED_CLASSES, type NodeProps } from "../utils/types";

/**
 * Switch node - Shows conditional branching with case rows inside
 * When there are few cases, shows numbered rows with condition previews
 * Supports highlighting when referenced in expressions
 */
const SwitchNode: React.FC<NodeProps> = ({ node, isSelected, isHighlighted, onClick }) => {
    const cases = node.data.cases || [];
    const hasDefault = !!node.data.defaultCase;
    const totalCases = cases.length + (hasDefault ? 1 : 0);

    return (
        <div
            className={`group relative cursor-pointer rounded-lg border-2 border-purple-500 bg-white shadow-sm transition-all duration-200 hover:shadow-md dark:border-purple-400 dark:bg-gray-800 ${
                isSelected ? NODE_SELECTED_CLASSES.PURPLE : ""
            } ${isHighlighted ? NODE_HIGHLIGHT_CLASSES : ""}`}
            style={{
                width: `${node.width}px`,
            }}
            onClick={e => {
                e.stopPropagation();
                onClick?.(node);
            }}
        >
            {/* Header */}
            <div className="flex items-center justify-between px-3 py-2">
                <div className="flex items-center gap-2">
                    <GitBranch className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                    <span className="text-sm font-medium text-purple-900 dark:text-purple-100">Switch</span>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500 dark:text-gray-400">{totalCases} cases</span>
                    <span className="rounded bg-purple-100 px-1.5 py-0.5 text-xs font-medium text-purple-700 dark:bg-purple-800/50 dark:text-purple-300">
                        Switch
                    </span>
                </div>
            </div>

            {/* Case rows */}
            {totalCases > 0 && (
                <div className="border-t border-purple-200 px-3 py-2 dark:border-purple-700/50">
                    <div className="flex flex-col gap-1.5">
                        {cases.map((caseItem: { condition?: string }, index: number) => (
                            <div key={index} className="flex items-center gap-2">
                                <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded bg-purple-100 text-xs font-medium text-purple-700 dark:bg-purple-800/50 dark:text-purple-300">
                                    {index + 1}
                                </span>
                                <span
                                    className="flex-1 truncate rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-700 dark:text-gray-400"
                                    title={caseItem.condition}
                                >
                                    {caseItem.condition || ""}
                                </span>
                            </div>
                        ))}
                        {hasDefault && (
                            <div className="flex items-center gap-2">
                                <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded bg-amber-100 text-xs font-medium text-amber-700 dark:bg-amber-800/50 dark:text-amber-300">
                                    {cases.length + 1}
                                </span>
                                <span className="flex-1 rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-500 dark:bg-gray-700 dark:text-gray-400">
                                    default
                                </span>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Node ID badge - fades in/out on hover */}
            <div className={NODE_ID_BADGE_CLASSES}>{node.id}</div>
        </div>
    );
};

export default SwitchNode;
