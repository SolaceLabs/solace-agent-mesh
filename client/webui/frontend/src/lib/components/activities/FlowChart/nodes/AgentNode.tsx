import { Fragment, useCallback } from "react";
import { Bot, Maximize2, Minimize2 } from "lucide-react";

import { Button } from "@/lib/components/ui";

import type { LayoutNode } from "../utils/types";
import { ACTIVITY_NODE_BASE_STYLES, ACTIVITY_NODE_SELECTED_CLASS, ACTIVITY_NODE_PROCESSING_CLASS, CONNECTOR_LINE_CLASSES, CONNECTOR_SIZES, ACTIVITY_NODE_LAYOUT, CONTAINER_CHILDREN_CLASSES } from "../utils/nodeStyles";
import { clickableNodeProps } from "@/lib/components/utils";
import LLMNode from "./LLMNode";
import ToolNode from "./ToolNode";
import SwitchNode from "./SwitchNode";
import LoopNode from "./LoopNode";
import WorkflowGroup from "./WorkflowGroup";
import { cn } from "@/lib";

interface AgentNodeProps {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
    onChildClick?: (child: LayoutNode) => void;
    onExpand?: (nodeId: string) => void;
    onCollapse?: (nodeId: string) => void;
}

const AgentNode = ({ node, isSelected, onClick, onChildClick, onExpand, onCollapse }: AgentNodeProps) => {
    // Reusable agent header with icon and label
    const AgentHeader = () => (
        <div className="flex min-w-0 items-center gap-2">
            <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-(--accent-n2-w10)">
                <Bot className="h-4 w-4 text-(--brand-wMain)" />
            </div>
            <div className="truncate text-sm font-semibold">{node.data.label}</div>
        </div>
    );

    // Render a child node recursively
    const renderChild = useCallback(
        (child: LayoutNode) => {
            const childProps = {
                node: child,
                onClick: onChildClick,
                onExpand,
                onCollapse,
            };

            switch (child.type) {
                case "agent":
                    // Recursive!
                    return <AgentNode key={child.id} {...childProps} onChildClick={onChildClick} />;
                case "llm":
                    return <LLMNode key={child.id} {...childProps} />;
                case "tool":
                    return <ToolNode key={child.id} {...childProps} />;
                case "switch":
                    return <SwitchNode key={child.id} {...childProps} />;
                case "loop":
                    return <LoopNode key={child.id} {...childProps} />;
                case "group":
                    return <WorkflowGroup key={child.id} {...childProps} onChildClick={onChildClick} />;
                case "parallelBlock":
                    // Don't render empty parallel blocks
                    if (child.children.length === 0) {
                        return null;
                    }
                    // Render parallel block - children displayed side-by-side with bounding box
                    return (
                        <div key={child.id} className={`flex flex-row items-start gap-4 p-4 ${CONTAINER_CHILDREN_CLASSES}`}>
                            {child.children.map(parallelChild => renderChild(parallelChild))}
                        </div>
                    );
                default:
                    return null;
            }
        },
        [onChildClick, onExpand, onCollapse]
    );

    // Pill variant for Start/Finish/Join/Map/Fork nodes
    if (node.data.variant === "pill") {
        const opacityClass = node.data.isSkipped ? "opacity-50" : "";
        const hasParallelBranches = node.parallelBranches && node.parallelBranches.length > 0;
        const hasChildren = node.children && node.children.length > 0;
        const isError = node.data.status === "error";

        // Color classes based on error status
        const pillColorClasses = isError ? "border-(--error-wMain) bg-(--error-w10) text-(--error-wMain)" : "border-(--info-wMain) bg-(--info-w10) text-(--info-wMain)";

        // If it's a simple pill (no parallel branches and no children), render compact version
        if (!hasParallelBranches && !hasChildren) {
            return (
                <div
                    className={cn(ACTIVITY_NODE_BASE_STYLES.PILL, pillColorClasses, isSelected && ACTIVITY_NODE_SELECTED_CLASS)}
                    style={{
                        width: `${node.width}px`,
                        minWidth: "80px",
                        textAlign: "center",
                    }}
                    title={node.data.description}
                >
                    <div className="flex items-center justify-center">
                        <div className="text-sm font-bold">{node.data.label}</div>
                    </div>
                </div>
            );
        }

        // Map/Fork pill with sequential children (flattened from parallel branches when detail is off)
        if (hasChildren && !hasParallelBranches) {
            return (
                <div className={`flex flex-col items-center ${opacityClass}`}>
                    {/* Pill label */}
                    <div
                        {...clickableNodeProps(() => onClick?.(node))}
                        className={`${ACTIVITY_NODE_BASE_STYLES.PILL} ${pillColorClasses} ${isSelected ? ACTIVITY_NODE_SELECTED_CLASS : ""}`}
                        style={{
                            minWidth: "80px",
                            textAlign: "center",
                        }}
                        title={node.data.description}
                    >
                        <div className="flex items-center justify-center">
                            <div className="text-sm font-bold">{node.data.label}</div>
                        </div>
                    </div>

                    {/* Connector line to children */}
                    <div className={`my-0 ${CONNECTOR_SIZES.MAIN} ${CONNECTOR_LINE_CLASSES}`} />

                    {/* Sequential children below */}
                    {node.children.map((child, index) => (
                        <Fragment key={child.id}>
                            {renderChild(child)}
                            {/* Connector line to next child */}
                            {index < node.children.length - 1 && <div className={`my-0 ${CONNECTOR_SIZES.MAIN} ${CONNECTOR_LINE_CLASSES}`} />}
                        </Fragment>
                    ))}
                </div>
            );
        }

        // Map/Fork pill with parallel branches
        return (
            <div className={`flex flex-col items-center ${opacityClass}`}>
                {/* Pill label */}
                <div
                    {...clickableNodeProps(() => onClick?.(node))}
                    className={`${ACTIVITY_NODE_BASE_STYLES.PILL} ${pillColorClasses} ${isSelected ? ACTIVITY_NODE_SELECTED_CLASS : ""}`}
                    style={{
                        minWidth: "80px",
                        textAlign: "center",
                    }}
                    title={node.data.description}
                >
                    <div className="flex items-center justify-center">
                        <div className="text-sm font-bold">{node.data.label}</div>
                    </div>
                </div>

                {/* Connector line to branches */}
                <div className={`my-0 ${CONNECTOR_SIZES.MAIN} ${CONNECTOR_LINE_CLASSES}`} />

                {/* Parallel branches below */}
                <div className={`rounded-md border-2 border-(--secondary-w20) bg-(--background-w20) p-4`}>
                    <div className="grid gap-4" style={{ gridAutoFlow: "column", gridAutoColumns: "1fr" }}>
                        {node.parallelBranches!.map((branch, branchIndex) => (
                            <div key={branchIndex} className="flex flex-col items-center">
                                {branch.map((child, index) => (
                                    <Fragment key={child.id}>
                                        {renderChild(child)}
                                        {/* Connector line to next child in branch */}
                                        {index < branch.length - 1 && <div className={`my-0 ${CONNECTOR_SIZES.MAIN} ${CONNECTOR_LINE_CLASSES}`} />}
                                    </Fragment>
                                ))}
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        );
    }

    // Regular agent node with children
    const opacityClass = node.data.isSkipped ? "opacity-50" : "";
    const borderStyleClass = node.data.isSkipped ? "border-dashed" : "border-solid";
    // Show effect if this node is processing OR if children are hidden but processing
    const isProcessing = node.data.status === "in-progress" || node.data.hasProcessingChildren;

    const haloClass = isProcessing ? ACTIVITY_NODE_PROCESSING_CLASS : "";

    const isCollapsed = node.data.isCollapsed;

    // Check if this is an expanded node (manually expanded from collapsed state)
    const isExpanded = node.data.isExpanded;

    const hasChildren = node.children && node.children.length > 0;
    const hasParallelBranches = node.parallelBranches && node.parallelBranches.length > 0;
    const hasContent = hasChildren || hasParallelBranches;

    // When collapsed or no children, render as simple rectangular node
    if (isCollapsed || !hasContent) {
        return (
            <div
                {...clickableNodeProps(() => onClick?.(node))}
                className={`${ACTIVITY_NODE_BASE_STYLES.RECTANGULAR} ${opacityClass} ${borderStyleClass} ${isSelected ? ACTIVITY_NODE_SELECTED_CLASS : ""} ${haloClass}`}
                style={{ minWidth: `${ACTIVITY_NODE_LAYOUT.CONTAINER_WIDTH}px`, minHeight: `${ACTIVITY_NODE_LAYOUT.LEAF_NODE_MIN_HEIGHT}px` }}
            >
                <AgentHeader />
                {/* Expand control */}
                {isCollapsed && onExpand && (
                    <Button
                        onClick={e => {
                            e.stopPropagation();
                            onExpand(node.id);
                        }}
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

    // When expanded with children, render with solid container and divider
    return (
        <div className={`flex flex-col ${opacityClass} ${haloClass}`}>
            {/* Solid Container with Header and Content */}
            <div className={`card-surface rounded bg-(--background-w10) transition-all duration-200 ${isSelected ? ACTIVITY_NODE_SELECTED_CLASS : ""}`} style={{ minWidth: `${ACTIVITY_NODE_LAYOUT.CONTAINER_WIDTH}px` }}>
                {/* Header */}
                <div {...clickableNodeProps(() => onClick?.(node))} className="group flex cursor-pointer items-center justify-between gap-4 px-4 py-2">
                    <AgentHeader />

                    {/* Collapse control */}
                    {isExpanded && onCollapse && (
                        <div className="opacity-0 transition-opacity group-hover:opacity-100">
                            <Button
                                onClick={e => {
                                    e.stopPropagation();
                                    onCollapse(node.id);
                                }}
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                tooltip="Collapse"
                            >
                                <Minimize2 className="h-4 w-4" />
                            </Button>
                        </div>
                    )}
                </div>

                {/* Divider */}
                <div className="border-t border-(--secondary-w20)" />

                {/* Children content */}
                <div className="bg-(--secondary-w20) p-4">
                    <div className="flex flex-col items-center gap-2">
                        {/* Sequential children */}
                        {hasChildren &&
                            node.children.map((child, index) => (
                                <Fragment key={child.id}>
                                    {renderChild(child)}
                                    {/* Connector line to next child */}
                                    {index < node.children.length - 1 && <div className={`my-0 ${CONNECTOR_SIZES.MAIN} ${CONNECTOR_LINE_CLASSES}`} />}
                                </Fragment>
                            ))}

                        {/* Parallel Branches */}
                        {hasParallelBranches && node.parallelBranches && (
                            <div className="mt-2 w-full rounded-md border-2 border-(--brand-w20) bg-(--background-w10) p-4">
                                <div className="grid gap-4" style={{ gridAutoFlow: "column", gridAutoColumns: "1fr" }}>
                                    {node.parallelBranches.map((branch, branchIndex) => (
                                        <div key={branchIndex} className="flex flex-col items-center">
                                            {branch.map((child, index) => (
                                                <Fragment key={child.id}>
                                                    {renderChild(child)}
                                                    {/* Connector line to next child in branch */}
                                                    {index < branch.length - 1 && <div className={`my-0 ${CONNECTOR_SIZES.MAIN} ${CONNECTOR_LINE_CLASSES}`} />}
                                                </Fragment>
                                            ))}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default AgentNode;
