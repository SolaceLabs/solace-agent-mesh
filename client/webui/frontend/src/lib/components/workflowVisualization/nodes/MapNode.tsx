import React from "react";
import { Repeat2, Maximize2, Minimize2 } from "lucide-react";
import type { NodeProps } from "../utils/types";

interface MapNodeProps extends NodeProps {
    renderChildren?: (children: NodeProps["node"]["children"]) => React.ReactNode;
}

/**
 * Map node - Container with dotted border for parallel execution over a collection
 * Shows expand/collapse icon and renders child nodes when expanded
 */
const MapNode: React.FC<MapNodeProps> = ({ node, isSelected, onClick, onExpand, onCollapse, renderChildren }) => {
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

    return (
        <div
            className={`relative rounded-lg border-2 border-dashed border-indigo-400 bg-indigo-50/30 transition-all duration-200 dark:border-indigo-600 dark:bg-indigo-900/20 ${
                isSelected ? "ring-2 ring-indigo-500 ring-offset-2 dark:ring-offset-gray-900" : ""
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
                    <Repeat2 className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                    <span className="text-sm font-medium text-indigo-900 dark:text-indigo-100">{node.data.label}</span>
                    <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-800/50 dark:text-indigo-300">
                        Map
                    </span>
                </div>

                {/* Expand/Collapse button */}
                {canHaveChildren && (
                    <button
                        onClick={handleToggle}
                        className="rounded p-1 text-indigo-500 hover:bg-indigo-100 dark:text-indigo-400 dark:hover:bg-indigo-800/50"
                        title={isCollapsed ? "Expand" : "Collapse"}
                    >
                        {isCollapsed ? <Maximize2 className="h-4 w-4" /> : <Minimize2 className="h-4 w-4" />}
                    </button>
                )}
            </div>

            {/* Children container */}
            {!isCollapsed && hasChildren && (
                <div className="px-3 pb-3">
                    <div className="flex flex-col items-center gap-2">
                        {renderChildren ? renderChildren(node.children) : null}
                    </div>
                </div>
            )}

            {/* Collapsed indicator */}
            {isCollapsed && canHaveChildren && (
                <div className="px-3 pb-3">
                    <div className="text-center text-xs text-indigo-500 dark:text-indigo-400">
                        Content hidden
                    </div>
                </div>
            )}
        </div>
    );
};

export default MapNode;
