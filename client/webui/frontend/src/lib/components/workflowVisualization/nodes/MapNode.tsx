import type { FC, ReactNode, MouseEvent } from "react";
import { Repeat2, Maximize2, Minimize2 } from "lucide-react";
import { NODE_HIGHLIGHT_CLASSES, NODE_SELECTED_CLASSES, type NodeProps } from "../utils/types";

interface MapNodeProps extends NodeProps {
    renderChildren?: (children: NodeProps["node"]["children"]) => ReactNode;
}

/**
 * Map node - Solid header box with dotted children container for parallel execution
 * Shows expand/collapse icon and renders child nodes when expanded
 * Supports highlighting when referenced in expressions
 */
const MapNode: FC<MapNodeProps> = ({ node, isSelected, isHighlighted, onClick, onExpand, onCollapse, renderChildren }) => {
    const isCollapsed = node.isCollapsed;
    const hasChildren = node.children && node.children.length > 0;
    // Check if node can have children (even when collapsed and children aren't loaded)
    const canHaveChildren = hasChildren || !!node.data.childNodeId;

    const handleToggle = (e: MouseEvent) => {
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
                className={`group relative flex cursor-pointer items-center justify-between rounded-lg border-2 border-(--color-accent-n1-wMain) bg-(--color-background-w10) px-3 py-2 shadow-sm transition-all duration-200 hover:shadow-md dark:border-(--color-accent-n1-w60) dark:bg-(--color-background-wMain) ${
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
                    <Repeat2 className="h-4 w-4 text-(--color-accent-n1-wMain) dark:text-(--color-accent-n1-w60)" />
                    <span className="text-sm font-medium text-(--color-accent-n1-w100) dark:text-(--color-accent-n1-w10)">Map</span>
                </div>

                {canHaveChildren && (
                    <button
                        onClick={handleToggle}
                        className="rounded p-1 text-(--color-accent-n1-wMain) hover:bg-(--color-accent-n1-w10) dark:text-(--color-accent-n1-w60) dark:hover:bg-(--color-accent-n1-w100)/50"
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
                className="absolute inset-0 rounded-lg border-2 border-dashed border-(--color-accent-n1-w30) bg-(--color-accent-n1-w10)/30 dark:border-(--color-accent-n1-w100)/50 dark:bg-(--color-accent-n1-w100)/10"
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
                className={`group relative mx-auto flex w-fit cursor-pointer items-center justify-between gap-4 rounded-lg border-2 border-(--color-accent-n1-wMain) bg-(--color-background-w10) px-3 py-2 shadow-sm transition-all duration-200 hover:shadow-md dark:border-(--color-accent-n1-w60) dark:bg-(--color-background-wMain) ${
                    isSelected ? NODE_SELECTED_CLASSES.INDIGO : ""
                } ${isHighlighted ? NODE_HIGHLIGHT_CLASSES : ""}`}
                onClick={e => {
                    e.stopPropagation();
                    onClick?.(node);
                }}
            >
                <div className="flex items-center gap-2">
                    <Repeat2 className="h-4 w-4 text-(--color-accent-n1-wMain) dark:text-(--color-accent-n1-w60)" />
                    <span className="text-sm font-medium text-(--color-accent-n1-w100) dark:text-(--color-accent-n1-w10)">Map</span>
                </div>

                <button
                    onClick={handleToggle}
                    className="rounded p-1 text-(--color-accent-n1-wMain) hover:bg-(--color-accent-n1-w10) dark:text-(--color-accent-n1-w60) dark:hover:bg-(--color-accent-n1-w100)/50"
                    title="Collapse"
                >
                    <Minimize2 className="h-4 w-4" />
                </button>
            </div>
        </div>
    );
};

export default MapNode;
