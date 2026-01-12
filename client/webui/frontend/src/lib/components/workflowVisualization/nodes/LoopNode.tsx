import React from "react";
import { RefreshCw, Maximize2, Minimize2 } from "lucide-react";
import type { NodeProps } from "../utils/types";

interface LoopNodeProps extends NodeProps {
    renderChildren?: (children: NodeProps["node"]["children"]) => React.ReactNode;
}

/**
 * Loop node - Container with dotted border for iterative execution
 * Shows condition, max iterations, expand/collapse icon, and renders child nodes when expanded
 */
const LoopNode: React.FC<LoopNodeProps> = ({ node, isSelected, onClick, onExpand, onCollapse, renderChildren }) => {
    const isCollapsed = node.isCollapsed;
    const hasChildren = node.children && node.children.length > 0;
    // Check if node can have children (even when collapsed and children aren't loaded)
    const canHaveChildren = hasChildren || !!node.data.childNodeId;

    const handleToggle = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (isCollapsed) {
            onExpand?.(node.id);
        } else {
            onCollapse?.(node.id);
        }
    };

    // Format condition for display (truncate if too long)
    const formatCondition = (condition?: string) => {
        if (!condition) return null;
        const maxLen = 30;
        return condition.length > maxLen ? `${condition.slice(0, maxLen)}...` : condition;
    };

    return (
        <div
            className={`relative rounded-lg border-2 border-dashed border-teal-400 bg-teal-50/30 transition-all duration-200 dark:border-teal-600 dark:bg-teal-900/20 ${
                isSelected ? "ring-2 ring-teal-500 ring-offset-2 dark:ring-offset-gray-900" : ""
            }`}
            style={{
                width: `${node.width}px`,
                minHeight: `${node.height}px`,
            }}
        >
            {/* Header */}
            <div
                className="flex cursor-pointer items-center justify-between rounded-t-md px-3 py-2"
                onClick={e => {
                    e.stopPropagation();
                    onClick?.(node);
                }}
            >
                <div className="flex items-center gap-2">
                    <RefreshCw className="h-4 w-4 text-teal-600 dark:text-teal-400" />
                    <span className="text-sm font-medium text-teal-900 dark:text-teal-100">{node.data.label}</span>
                    <span className="rounded bg-teal-100 px-1.5 py-0.5 text-xs font-medium text-teal-700 dark:bg-teal-800/50 dark:text-teal-300">
                        Loop
                    </span>
                </div>

                {/* Expand/Collapse button */}
                {canHaveChildren && (
                    <button
                        onClick={handleToggle}
                        className="rounded p-1 text-teal-500 hover:bg-teal-100 dark:text-teal-400 dark:hover:bg-teal-800/50"
                        title={isCollapsed ? "Expand" : "Collapse"}
                    >
                        {isCollapsed ? <Maximize2 className="h-4 w-4" /> : <Minimize2 className="h-4 w-4" />}
                    </button>
                )}
            </div>

            {/* Condition display */}
            {(node.data.condition || node.data.maxIterations) && (
                <div className="border-t border-teal-200 px-3 py-1.5 dark:border-teal-700/50">
                    <div className="flex flex-wrap gap-2 text-xs text-teal-600 dark:text-teal-400">
                        {node.data.condition && (
                            <span className="truncate" title={node.data.condition}>
                                while: {formatCondition(node.data.condition)}
                            </span>
                        )}
                        {node.data.maxIterations && <span>max: {node.data.maxIterations}</span>}
                    </div>
                </div>
            )}

            {/* Children container */}
            {!isCollapsed && hasChildren && (
                <div className="px-3 pb-3 pt-2">
                    <div className="flex flex-col items-center gap-2">
                        {renderChildren ? renderChildren(node.children) : null}
                    </div>
                </div>
            )}

            {/* Collapsed indicator */}
            {isCollapsed && canHaveChildren && (
                <div className="px-3 pb-3">
                    <div className="text-center text-xs text-teal-500 dark:text-teal-400">
                        Content hidden
                    </div>
                </div>
            )}
        </div>
    );
};

export default LoopNode;
