import { Fragment, type FC } from "react";
import { Bot, Maximize2, Minimize2 } from "lucide-react";

import { Button } from "@/lib/components/ui";

import type { LayoutNode } from "../utils/types";
import { ACTIVITY_NODE_BASE_STYLES, ACTIVITY_NODE_SELECTED_CLASS, ACTIVITY_NODE_PROCESSING_CLASS, CONNECTOR_LINE_CLASSES, CONNECTOR_SIZES } from "../utils/nodeStyles";
import LLMNode from "./LLMNode";
import ToolNode from "./ToolNode";
import SwitchNode from "./SwitchNode";
import LoopNode from "./LoopNode";
import WorkflowGroup from "./WorkflowGroup";

interface AgentNodeProps {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
    onChildClick?: (child: LayoutNode) => void;
    onExpand?: (nodeId: string) => void;
    onCollapse?: (nodeId: string) => void;
}

const AgentNode: FC<AgentNodeProps> = ({ node, isSelected, onClick, onChildClick, onExpand, onCollapse }) => {
    // Render a child node recursively
    const renderChild = (child: LayoutNode) => {
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
                    <div key={child.id} className="flex flex-row items-start gap-4 rounded-lg border-2 border-dashed border-gray-300 bg-gray-50/50 p-4 dark:border-gray-600 dark:bg-gray-800/50">
                        {child.children.map(parallelChild => renderChild(parallelChild))}
                    </div>
                );
            default:
                return null;
        }
    };

    // Pill variant for Start/Finish/Join/Map/Fork nodes
    if (node.data.variant === "pill") {
        const opacityClass = node.data.isSkipped ? "opacity-50" : "";
        const borderStyleClass = node.data.isSkipped ? "border-dashed" : "border-solid";
        const hasParallelBranches = node.parallelBranches && node.parallelBranches.length > 0;
        const hasChildren = node.children && node.children.length > 0;
        const isError = node.data.status === "error";

        // Color classes based on error status
        const pillColorClasses = isError
            ? "border-red-500 bg-red-50 text-red-900 dark:border-red-400 dark:bg-red-900/50 dark:text-red-100"
            : "border-indigo-500 bg-indigo-50 text-indigo-900 dark:border-indigo-400 dark:bg-indigo-900/50 dark:text-indigo-100";

        // If it's a simple pill (no parallel branches and no children), render compact version
        if (!hasParallelBranches && !hasChildren) {
            return (
                <div
                    className={`${ACTIVITY_NODE_BASE_STYLES.PILL} border-2 ${pillColorClasses} ${opacityClass} ${borderStyleClass} ${
                        isSelected ? ACTIVITY_NODE_SELECTED_CLASS : ""
                    }`}
                    style={{
                        width: `${node.width}px`,
                        minWidth: "80px",
                        textAlign: "center",
                    }}
                    onClick={e => {
                        e.stopPropagation();
                        onClick?.(node);
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
                <div className={`flex flex-col items-center ${opacityClass} ${borderStyleClass}`}>
                    {/* Pill label */}
                    <div
                        className={`${ACTIVITY_NODE_BASE_STYLES.PILL} border-2 ${pillColorClasses} ${isSelected ? ACTIVITY_NODE_SELECTED_CLASS : ""}`}
                        style={{
                            minWidth: "80px",
                            textAlign: "center",
                        }}
                        onClick={e => {
                            e.stopPropagation();
                            onClick?.(node);
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
            <div className={`flex flex-col items-center ${opacityClass} ${borderStyleClass}`}>
                {/* Pill label */}
                <div
                    className={`${ACTIVITY_NODE_BASE_STYLES.PILL} border-2 ${pillColorClasses} ${isSelected ? ACTIVITY_NODE_SELECTED_CLASS : ""}`}
                    style={{
                        minWidth: "80px",
                        textAlign: "center",
                    }}
                    onClick={e => {
                        e.stopPropagation();
                        onClick?.(node);
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
                <div className="rounded-md border-2 border-indigo-200 bg-white p-4 dark:border-indigo-800 dark:bg-gray-800">
                    <div className="grid gap-4" style={{ gridAutoFlow: "column", gridAutoColumns: "1fr" }}>
                        {node.parallelBranches!.map((branch, branchIndex) => (
                            <div key={branchIndex} className="flex flex-col items-center">
                                {branch.map((child, index) => (
                                    <Fragment key={child.id}>
                                        {renderChild(child)}
                                        {/* Connector line to next child in branch */}
                                        {index < branch.length - 1 && <div className="my-0 h-4 w-0.5 bg-gray-400 dark:bg-gray-600" />}
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

    return (
        <div
            className={`${ACTIVITY_NODE_BASE_STYLES.RECTANGULAR} ${opacityClass} ${borderStyleClass} ${
                isSelected ? ACTIVITY_NODE_SELECTED_CLASS : ""
            } ${haloClass}`}
            style={{
                minWidth: "180px",
            }}
        >
            {/* Header */}
            <div
                className={`cursor-pointer ${
                    node.children.length === 0 && (!node.parallelBranches || node.parallelBranches.length === 0)
                        ? "rounded-md" // No content below, round all corners
                        : "rounded-t-md" // Content below, round only top
                }`}
                onClick={e => {
                    e.stopPropagation();
                    onClick?.(node);
                }}
                title={node.data.description}
            >
                <div className="flex items-center justify-between gap-2">
                    <div className="flex min-w-0 items-center gap-2">
                        <Bot className="h-4 w-4 flex-shrink-0 text-(--color-brand-wMain)" />
                        <div className="truncate text-sm font-semibold">{node.data.label}</div>
                    </div>
                    {/* Expand/Collapse controls */}
                    {((isCollapsed && onExpand) || (isExpanded && onCollapse)) && (
                        <div className={isExpanded && onCollapse ? "opacity-0 transition-opacity group-hover:opacity-100" : ""}>
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
                            {isExpanded && onCollapse && (
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
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* Content - Children with inline connectors */}
            {node.children.length > 0 && (
                <div className={`flex flex-col items-center p-4 ${!node.parallelBranches || node.parallelBranches.length === 0 ? "rounded-b-md" : ""}`}>
                    {node.children.map((child, index) => (
                        <Fragment key={child.id}>
                            {renderChild(child)}
                            {/* Connector line to next child */}
                            {index < node.children.length - 1 && <div className={`my-0 ${CONNECTOR_SIZES.MAIN} ${CONNECTOR_LINE_CLASSES}`} />}
                        </Fragment>
                    ))}
                </div>
            )}

            {/* Parallel Branches */}
            {node.parallelBranches && node.parallelBranches.length > 0 && (
                <div className="rounded-b-md border-t-2 border-(--color-brand-w20) p-4 dark:border-(--color-brand-w80)">
                    <div className="grid gap-4" style={{ gridAutoFlow: "column", gridAutoColumns: "1fr" }}>
                        {node.parallelBranches.map((branch, branchIndex) => (
                            <div key={branchIndex} className="flex flex-col items-center">
                                {branch.map((child, index) => (
                                    <Fragment key={child.id}>
                                        {renderChild(child)}
                                        {/* Connector line to next child in branch */}
                                        {index < branch.length - 1 && <div className="my-0 h-4 w-0.5 bg-gray-400 dark:bg-gray-600" />}
                                    </Fragment>
                                ))}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default AgentNode;
