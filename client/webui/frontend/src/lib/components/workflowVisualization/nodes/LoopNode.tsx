import React from "react";
import { RefreshCw, Maximize2, Minimize2 } from "lucide-react";
import { NODE_HIGHLIGHT_CLASSES, NODE_SELECTED_CLASSES, type NodeProps } from "../utils/types";

interface LoopNodeProps extends NodeProps {
    renderChildren?: (children: NodeProps["node"]["children"]) => React.ReactNode;
}

/**
 * Loop node - Solid header box with dotted children container for iterative execution
 * Shows condition, max iterations, expand/collapse icon, and renders child nodes when expanded
 * Supports highlighting when referenced in expressions
 */
const LoopNode: React.FC<LoopNodeProps> = ({ node, isSelected, isHighlighted, onClick, onExpand, onCollapse, renderChildren }) => {
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

    const hasConditionRow = node.data.condition || node.data.maxIterations;

    // When collapsed or no children, render as a simple node (like AgentNode)
    if (isCollapsed || !hasChildren) {
        return (
            <div
                className={`group relative flex cursor-pointer items-center justify-between rounded-lg border-2 border-teal-500 bg-white px-3 py-2 shadow-sm transition-all duration-200 hover:shadow-md dark:border-teal-400 dark:bg-gray-800 ${
                    isSelected ? NODE_SELECTED_CLASSES.TEAL : ""
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
                <div className="flex items-center gap-2">
                    <RefreshCw className="h-4 w-4 text-teal-600 dark:text-teal-400" />
                    <span className="text-sm font-medium text-teal-900 dark:text-teal-100">Loop</span>
                </div>

                {canHaveChildren && (
                    <button
                        onClick={handleToggle}
                        className="rounded p-1 text-teal-500 hover:bg-teal-100 dark:text-teal-400 dark:hover:bg-teal-800/50"
                        title="Expand"
                    >
                        <Maximize2 className="h-4 w-4" />
                    </button>
                )}

            </div>
        );
    }

    // Calculate header height for straddling effect
    // Header row: py-2 (16px) + icon line (~20px) ≈ 36px
    // Condition row adds: border + py-1.5 (12px) + text (~16px) ≈ 28px
    // Dotted border starts closer to top for better visual balance
    const headerHeightPx = hasConditionRow ? 64 : 36;
    const headerTopOffsetPx = headerHeightPx / 3;

    // When expanded with children, render with straddling header and dotted container
    return (
        <div
            className="relative"
            style={{
                width: `${node.width}px`,
                height: `${node.height}px`,
            }}
        >
            {/* Dotted Children Container */}
            <div
                className="absolute inset-0 rounded-lg border-2 border-dashed border-teal-300 bg-teal-50/30 dark:border-teal-600/50 dark:bg-teal-900/10"
                style={{ top: `${headerTopOffsetPx}px` }}
            >
                {/* Top padding clears the header portion below the dotted border plus gap */}
                <div className={`pb-4 px-3 ${hasConditionRow ? 'pt-16' : 'pt-12'}`}>
                    <div className="flex flex-col items-center gap-2">
                        {renderChildren ? renderChildren(node.children) : null}
                    </div>
                </div>
            </div>

            {/* Solid Header Box - straddles the dotted container border */}
            <div
                className={`group relative mx-auto w-fit cursor-pointer rounded-lg border-2 border-teal-500 bg-white shadow-sm transition-all duration-200 hover:shadow-md dark:border-teal-400 dark:bg-gray-800 ${
                    isSelected ? NODE_SELECTED_CLASSES.TEAL : ""
                } ${isHighlighted ? NODE_HIGHLIGHT_CLASSES : ""}`}
                onClick={e => {
                    e.stopPropagation();
                    onClick?.(node);
                }}
            >
                {/* Header row */}
                <div className="flex items-center justify-between gap-4 px-3 py-2">
                    <div className="flex items-center gap-2">
                        <RefreshCw className="h-4 w-4 text-teal-600 dark:text-teal-400" />
                        <span className="text-sm font-medium text-teal-900 dark:text-teal-100">Loop</span>
                    </div>

                    <button
                        onClick={handleToggle}
                        className="rounded p-1 text-teal-500 hover:bg-teal-100 dark:text-teal-400 dark:hover:bg-teal-800/50"
                        title="Collapse"
                    >
                        <Minimize2 className="h-4 w-4" />
                    </button>
                </div>

                {/* Condition display */}
                {hasConditionRow && (
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

            </div>
        </div>
    );
};

export default LoopNode;
