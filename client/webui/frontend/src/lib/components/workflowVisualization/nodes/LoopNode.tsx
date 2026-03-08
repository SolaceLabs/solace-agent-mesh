import type { FC, ReactNode, MouseEvent } from "react";
import { RefreshCw, Maximize2, Minimize2 } from "lucide-react";
import { Button } from "@/lib/components/ui";
import { NODE_BASE_STYLES, NODE_HIGHLIGHT_CLASSES, NODE_SELECTED_CLASS, LAYOUT_CONSTANTS, type NodeProps } from "../utils/types";

const { NODE_HEIGHTS } = LAYOUT_CONSTANTS;

interface LoopNodeProps extends NodeProps {
    renderChildren?: (children: NodeProps["node"]["children"]) => ReactNode;
}

/**
 * Loop node - Solid header box with dotted children container for iterative execution
 * Shows condition, max iterations, expand/collapse icon, and renders child nodes when expanded
 * Supports highlighting when referenced in expressions
 */
const LoopNode: FC<LoopNodeProps> = ({ node, isSelected, isHighlighted, onClick, onExpand, onCollapse, renderChildren }) => {
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
                className={`${NODE_BASE_STYLES.RECTANGULAR_COMPACT} ${isSelected ? NODE_SELECTED_CLASS : ""} ${isHighlighted ? NODE_HIGHLIGHT_CLASSES : ""}`}
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
                    <span className="text-sm font-semibold">Loop</span>
                </div>

                <div className="flex items-center gap-2">
                    {node.data.maxIterations && <span className="text-sm text-gray-500 dark:text-gray-400">max: {node.data.maxIterations}</span>}
                    {canHaveChildren && (
                        <Button onClick={handleToggle} variant="ghost" size="icon" className="h-8 w-8" tooltip="Expand">
                            <Maximize2 className="h-4 w-4" />
                        </Button>
                    )}
                </div>
            </div>
        );
    }

    // Calculate header section height for positioning dotted container
    // Header row is CONTAINER_HEADER (44px), plus condition section if present (44px)
    const hasCondition = !!node.data.condition;
    const totalHeaderHeightPx = NODE_HEIGHTS.CONTAINER_HEADER + (hasCondition ? NODE_HEIGHTS.LOOP_CONDITION_ROW : 0);

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
                className="absolute inset-0 rounded border-1 border-dashed border-(--color-secondary-w40) bg-(--color-secondary-w10) dark:border-(--color-secondary-w70) dark:bg-(--color-secondary-w100)"
                style={{ top: `${totalHeaderHeightPx / 2}px` }}
            >
                {/* Top padding clears the header portion below the dotted border plus gap */}
                <div className={`px-3 pb-4 ${hasConditionRow ? "pt-16" : "pt-12"}`}>
                    <div className="flex flex-col items-center gap-2">{renderChildren ? renderChildren(node.children) : null}</div>
                </div>
            </div>

            {/* Solid Header Box - straddles the dotted container border */}
            <div
                className={`${NODE_BASE_STYLES.CONTAINER_HEADER} ${isSelected ? NODE_SELECTED_CLASS : ""} ${isHighlighted ? NODE_HIGHLIGHT_CLASSES : ""}`}
                onClick={e => {
                    e.stopPropagation();
                    onClick?.(node);
                }}
            >
                {/* Header row */}
                <div className="flex items-center justify-between gap-4 px-4 py-2">
                    <div className="flex items-center gap-2">
                        <RefreshCw className="h-4 w-4 text-(--color-accent-n0-wMain)" />
                        <span className="text-sm font-semibold">Loop</span>
                    </div>

                    <div className="flex items-center gap-2">
                        {node.data.maxIterations && <span className="text-sm text-gray-500 dark:text-gray-400">max: {node.data.maxIterations}</span>}
                        <Button onClick={handleToggle} variant="ghost" size="icon" className="h-8 w-8" tooltip="Collapse">
                            <Minimize2 className="h-4 w-4" />
                        </Button>
                    </div>
                </div>

                {/* Condition display */}
                {hasConditionRow && (
                    <div className="px-4 pt-0 pb-3">
                        <span className="text-secondary-foreground block truncate rounded bg-(--color-secondary-w10) px-2 py-1 text-sm dark:bg-(--color-secondary-w80)" title={node.data.condition}>
                            while: {formatCondition(node.data.condition)}
                        </span>
                    </div>
                )}
            </div>
        </div>
    );
};

export default LoopNode;
