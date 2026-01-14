import React from "react";
import { Repeat2, Maximize2, Minimize2 } from "lucide-react";
import { NODE_HIGHLIGHT_CLASSES, NODE_SELECTED_CLASSES, type NodeProps } from "../utils/types";

interface MapNodeProps extends NodeProps {
    renderChildren?: (children: NodeProps["node"]["children"]) => React.ReactNode;
}

/**
 * Map node - Solid header box with dotted children container for parallel execution
 * Shows expand/collapse icon and renders child nodes when expanded
 * Supports highlighting when referenced in expressions
 */
const MapNode: React.FC<MapNodeProps> = ({ node, isSelected, isHighlighted, onClick, onExpand, onCollapse, renderChildren }) => {
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

    // When collapsed, render as a simple node (like AgentNode)
    if (isCollapsed || !hasChildren) {
        return (
            <div
                className={`group relative flex cursor-pointer items-center justify-between rounded-lg border-2 border-indigo-500 bg-white px-3 py-2 shadow-sm transition-all duration-200 hover:shadow-md dark:border-indigo-400 dark:bg-gray-800 ${
                    isSelected ? NODE_SELECTED_CLASSES.INDIGO : ""
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
                    <Repeat2 className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                    <span className="text-sm font-medium text-indigo-900 dark:text-indigo-100">Map</span>
                </div>

                {canHaveChildren && (
                    <button
                        onClick={handleToggle}
                        className="rounded p-1 text-indigo-500 hover:bg-indigo-100 dark:text-indigo-400 dark:hover:bg-indigo-800/50"
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
    // Dotted border starts closer to top for better visual balance
    const headerHeightPx = 36;
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
                className="absolute inset-0 rounded-lg border-2 border-dashed border-indigo-300 bg-indigo-50/30 dark:border-indigo-600/50 dark:bg-indigo-900/10"
                style={{ top: `${headerTopOffsetPx}px` }}
            >
                {/* Top padding clears the header portion below the dotted border plus gap */}
                <div className="pt-12 pb-4 px-3">
                    <div className="flex flex-col items-center gap-2">
                        {renderChildren ? renderChildren(node.children) : null}
                    </div>
                </div>
            </div>

            {/* Solid Header Box - straddles the dotted container border */}
            <div
                className={`group relative mx-auto flex w-fit cursor-pointer items-center justify-between gap-4 rounded-lg border-2 border-indigo-500 bg-white px-3 py-2 shadow-sm transition-all duration-200 hover:shadow-md dark:border-indigo-400 dark:bg-gray-800 ${
                    isSelected ? NODE_SELECTED_CLASSES.INDIGO : ""
                } ${isHighlighted ? NODE_HIGHLIGHT_CLASSES : ""}`}
                onClick={e => {
                    e.stopPropagation();
                    onClick?.(node);
                }}
            >
                <div className="flex items-center gap-2">
                    <Repeat2 className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                    <span className="text-sm font-medium text-indigo-900 dark:text-indigo-100">Map</span>
                </div>

                <button
                    onClick={handleToggle}
                    className="rounded p-1 text-indigo-500 hover:bg-indigo-100 dark:text-indigo-400 dark:hover:bg-indigo-800/50"
                    title="Collapse"
                >
                    <Minimize2 className="h-4 w-4" />
                </button>

            </div>
        </div>
    );
};

export default MapNode;
