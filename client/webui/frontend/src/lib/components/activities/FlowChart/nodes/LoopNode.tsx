import { Fragment, type FC } from "react";
import { RefreshCw } from "lucide-react";

import type { LayoutNode } from "../utils/types";
import { ACTIVITY_NODE_BASE_STYLES, ACTIVITY_NODE_SELECTED_CLASS, CONNECTOR_LINE_CLASSES, CONNECTOR_SIZES } from "../utils/nodeStyles";
import AgentNode from "./AgentNode";

interface LoopNodeProps {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
    onChildClick?: (child: LayoutNode) => void;
    onExpand?: (nodeId: string) => void;
    onCollapse?: (nodeId: string) => void;
}

const LoopNode: FC<LoopNodeProps> = ({ node, isSelected, onClick, onChildClick, onExpand, onCollapse }) => {
    const currentIteration = node.data.currentIteration ?? 0;
    const maxIterations = node.data.maxIterations ?? 100;
    const hasChildren = node.children && node.children.length > 0;

    // Layout constants
    const LOOP_WIDTH = 280; // Static width for loop nodes
    const HEADER_HEIGHT = 44;

    // Render a child node (loop iterations are agent nodes)
    const renderChild = (child: LayoutNode) => {
        const childProps = {
            node: child,
            onClick: onChildClick,
            onChildClick: onChildClick,
            onExpand,
            onCollapse,
        };

        switch (child.type) {
            case "agent":
                return <AgentNode key={child.id} {...childProps} />;
            default:
                // Loop children are typically agents, but handle other types if needed
                return null;
        }
    };

    // Format condition for display (truncate if too long)
    const formatCondition = (condition?: string) => {
        if (!condition) return null;
        const maxLen = 30;
        return condition.length > maxLen ? `${condition.slice(0, maxLen)}...` : condition;
    };

    // If the node has children (iterations), render as expanded container with dotted border
    if (hasChildren) {
        const hasConditionRow = node.data.condition || maxIterations;

        return (
            <div className="flex flex-col px-4" style={{ minWidth: `${LOOP_WIDTH + 72}px` }}>
                {/* Solid Header Box - positioned at top, centered with fixed width */}
                <div
                    className={`${ACTIVITY_NODE_BASE_STYLES.CONTAINER_HEADER} ${isSelected ? ACTIVITY_NODE_SELECTED_CLASS : ""}`}
                    style={{ width: `${LOOP_WIDTH}px` }}
                    onClick={e => {
                        e.stopPropagation();
                        onClick?.(node);
                    }}
                >
                    {/* Header row */}
                    <div className="flex items-center gap-4 px-4 py-2">
                        <div className="flex items-center gap-2">
                            <RefreshCw className="h-4 w-4 text-(--color-accent-n0-wMain)" />
                            <span className="text-sm font-semibold">{node.data.label || "Loop"}</span>
                        </div>
                        {maxIterations && <span className="text-sm text-gray-500 dark:text-gray-400">max: {maxIterations}</span>}
                    </div>

                    {/* Condition display */}
                    {hasConditionRow && node.data.condition && (
                        <div className="px-4 pt-0 pb-3">
                            <span className="text-secondary-foreground block truncate rounded bg-(--color-secondary-w10) px-2 py-1 text-sm dark:bg-(--color-secondary-w80)" title={node.data.condition}>
                                while: {formatCondition(node.data.condition)}
                            </span>
                        </div>
                    )}
                </div>

                {/* Dotted Children Container - grows with content */}
                <div
                    className="rounded border-1 border-dashed border-(--color-secondary-w40) bg-(--color-stateLayer-w10) dark:border-(--color-secondary-w70) dark:bg-(--color-secondary-w100)"
                    style={{ marginTop: `-${HEADER_HEIGHT / 2}px`, paddingTop: `${HEADER_HEIGHT / 2 + (hasConditionRow ? 32 : 16)}px`, minWidth: `${LOOP_WIDTH + 72}px` }}
                >
                    <div className="px-3 pb-4">
                        <div className="flex flex-col items-center gap-2">
                            {node.children.map((child, index) => (
                                <Fragment key={child.id}>
                                    {renderChild(child)}
                                    {/* Connector line to next iteration */}
                                    {index < node.children.length - 1 && <div className={`my-1 ${CONNECTOR_SIZES.MAIN} ${CONNECTOR_LINE_CLASSES}`} />}
                                </Fragment>
                            ))}

                            {/* Iteration Counter (if in progress and more iterations coming) */}
                            {node.data.status === "in-progress" && currentIteration > node.children.length && (
                                <div className="mt-2 rounded bg-(--color-background-w10) px-2 py-1 text-[9px] font-medium text-gray-600 dark:bg-(--color-background-wMain) dark:text-gray-300">Processing iteration {currentIteration}...</div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    // No children - render as compact node
    return (
        <div
            className={`${ACTIVITY_NODE_BASE_STYLES.RECTANGULAR} ${isSelected ? ACTIVITY_NODE_SELECTED_CLASS : ""}`}
            style={{ width: "fit-content", minWidth: "120px" }}
            onClick={e => {
                e.stopPropagation();
                onClick?.(node);
            }}
        >
            <div className="flex items-center gap-2">
                <RefreshCw className="h-4 w-4 text-teal-600 dark:text-teal-400" />
                <span className="text-sm font-semibold">Loop</span>
            </div>
            {maxIterations && <span className="text-sm text-gray-500 dark:text-gray-400">max: {maxIterations}</span>}
        </div>
    );
};

export default LoopNode;
