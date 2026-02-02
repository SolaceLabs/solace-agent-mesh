import type { FC, ReactNode, MouseEvent } from "react";
import { Repeat2, Maximize2, Minimize2 } from "lucide-react";
import { Button } from "@/lib/components/ui";
import { NODE_BASE_STYLES, NODE_HIGHLIGHT_CLASSES, NODE_SELECTED_CLASS, LAYOUT_CONSTANTS, type NodeProps } from "../utils/types";

const { NODE_HEIGHTS } = LAYOUT_CONSTANTS;

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
                className={`${NODE_BASE_STYLES.RECTANGULAR_COMPACT}  ${
                    isSelected ? NODE_SELECTED_CLASS : ""
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
                    <span className="text-sm font-semibold text-indigo-900 dark:text-indigo-100">Map</span>
                </div>

                {canHaveChildren && (
                    <Button
                        onClick={handleToggle}
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        tooltip="Expand"
                    >
                        <Maximize2 className="h-4 w-4" />
                    </Button>
                )}
            </div>
        );
    }

    // When expanded with children, render with straddling header and dotted container
    return (
        <div
            className="relative "
            style={{
                width: `${node.width}px`,
                height: `${node.height}px`,
            }}
        >
            {/* Dotted Children Container */}
            <div
                className="absolute inset-0 rounded border-1 border-dashed border-(--color-secondary-w40) bg-(--color-secondary-w10) dark:bg-(--color-secondary-w100) dark:border-(--color-secondary-w80)"
                style={{ top: `${NODE_HEIGHTS.CONTAINER_HEADER / 2}px` }}
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
                className={`${NODE_BASE_STYLES.CONTAINER_HEADER} ${
                    isSelected ? NODE_SELECTED_CLASS : ""
                } ${isHighlighted ? NODE_HIGHLIGHT_CLASSES : ""}`}
                onClick={e => {
                    e.stopPropagation();
                    onClick?.(node);
                }}
            >
                <div className="flex items-center justify-between gap-4 px-4 py-2">
                    <div className="flex items-center gap-2">
                        <Repeat2 className="h-4 w-4 text-(--color-accent-n0-wMain)" />
                        <span className="text-sm font-semibold">Map</span>
                    </div>

                    <Button
                        onClick={handleToggle}
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        tooltip="Collapse"
                    >
                        <Minimize2 className="h-4 w-4" />
                    </Button>
                </div>
            </div>
        </div>
    );
};

export default MapNode;
