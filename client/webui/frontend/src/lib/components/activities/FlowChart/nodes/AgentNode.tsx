import { Fragment, type FC } from "react";
import { Bot, Maximize2, Minimize2 } from "lucide-react";
import type { LayoutNode } from "../utils/types";
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
            case 'agent':
                // Recursive!
                return <AgentNode key={child.id} {...childProps} onChildClick={onChildClick} />;
            case 'llm':
                return <LLMNode key={child.id} {...childProps} />;
            case 'tool':
                return <ToolNode key={child.id} {...childProps} />;
            case 'switch':
                return <SwitchNode key={child.id} {...childProps} />;
            case 'loop':
                return <LoopNode key={child.id} {...childProps} />;
            case 'group':
                return <WorkflowGroup key={child.id} {...childProps} onChildClick={onChildClick} />;
            case 'parallelBlock':
                // Render parallel block - children displayed side-by-side with bounding box
                return (
                    <div
                        key={child.id}
                        className="flex flex-row items-start gap-4 p-4 border-2 border-dashed border-(--color-secondary-w40) dark:border-(--color-secondary-w70) rounded-lg bg-(--color-secondary-w10)/50 dark:bg-(--color-background-wMain)/50"
                    >
                        {child.children.map((parallelChild) => renderChild(parallelChild))}
                    </div>
                );
            default:
                return null;
        }
    };

    // Pill variant for Start/Finish/Join/Map/Fork nodes
    if (node.data.variant === 'pill') {
        const opacityClass = node.data.isSkipped ? "opacity-50" : "";
        const borderStyleClass = node.data.isSkipped ? "border-dashed" : "border-solid";
        const hasParallelBranches = node.parallelBranches && node.parallelBranches.length > 0;
        const hasChildren = node.children && node.children.length > 0;
        const isError = node.data.status === 'error';

        // Color classes based on error status
        const pillColorClasses = isError
            ? "border-(--color-error-wMain) bg-(--color-error-w10) text-(--color-error-w100) dark:border-(--color-error-w70) dark:bg-(--color-error-w100)/50 dark:text-(--color-error-w10)"
            : "border-(--color-accent-n1-wMain) bg-(--color-accent-n1-w10) text-(--color-accent-n1-w100) dark:border-(--color-accent-n1-w60) dark:bg-(--color-accent-n1-w100)/50 dark:text-(--color-accent-n1-w10)";

        // If it's a simple pill (no parallel branches and no children), render compact version
        if (!hasParallelBranches && !hasChildren) {
            return (
                <div
                    className={`cursor-pointer rounded-full border-2 px-4 py-2 shadow-sm transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-md ${pillColorClasses} ${opacityClass} ${borderStyleClass} ${
                        isSelected ? "ring-2 ring-blue-500" : ""
                    }`}
                    style={{
                        width: `${node.width}px`,
                        minWidth: "80px",
                        textAlign: "center",
                    }}
                    onClick={(e) => {
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
                        className={`cursor-pointer rounded-full border-2 px-4 py-2 shadow-sm transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-md ${pillColorClasses} ${
                            isSelected ? "ring-2 ring-blue-500" : ""
                        }`}
                        style={{
                            minWidth: "80px",
                            textAlign: "center",
                        }}
                        onClick={(e) => {
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
                    <div className="w-0.5 h-4 bg-(--color-secondary-w40) dark:bg-(--color-secondary-w70) my-0" />

                    {/* Sequential children below */}
                    {node.children.map((child, index) => (
                        <Fragment key={child.id}>
                            {renderChild(child)}
                            {/* Connector line to next child */}
                            {index < node.children.length - 1 && (
                                <div className="w-0.5 h-4 bg-(--color-secondary-w40) dark:bg-(--color-secondary-w70) my-0" />
                            )}
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
                    className={`cursor-pointer rounded-full border-2 px-4 py-2 shadow-sm transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-md ${pillColorClasses} ${
                        isSelected ? "ring-2 ring-blue-500" : ""
                    }`}
                    style={{
                        minWidth: "80px",
                        textAlign: "center",
                    }}
                    onClick={(e) => {
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
                <div className="w-0.5 h-4 bg-(--color-secondary-w40) dark:bg-(--color-secondary-w70) my-0" />

                {/* Parallel branches below */}
                <div className="p-4 border-2 border-(--color-accent-n1-w30) dark:border-(--color-accent-n1-w100) rounded-md bg-(--color-background-w10) dark:bg-(--color-background-wMain)">
                    <div className="grid gap-4" style={{ gridAutoFlow: 'column', gridAutoColumns: '1fr' }}>
                        {node.parallelBranches!.map((branch, branchIndex) => (
                            <div key={branchIndex} className="flex flex-col items-center">
                                {branch.map((child, index) => (
                                    <Fragment key={child.id}>
                                        {renderChild(child)}
                                        {/* Connector line to next child in branch */}
                                        {index < branch.length - 1 && (
                                            <div className="w-0.5 h-4 bg-(--color-secondary-w40) dark:bg-(--color-secondary-w70) my-0" />
                                        )}
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

    const haloClass = isProcessing ? 'processing-halo' : '';

    const isCollapsed = node.data.isCollapsed;

    // Check if this is an expanded node (manually expanded from collapsed state)
    const isExpanded = node.data.isExpanded;

    return (
        <div
            className={`group relative rounded-md border-2 border-(--color-info-w100) bg-(--color-background-w10) shadow-md transition-all duration-200 ease-in-out hover:shadow-xl dark:border-(--color-info-wMain) dark:bg-(--color-background-wMain) ${opacityClass} ${borderStyleClass} ${
                isSelected ? "ring-2 ring-blue-500" : ""
            } ${haloClass}`}
            style={{
                minWidth: "180px",
            }}
        >
            {/* Collapse icon - top right, only show on hover when expanded */}
            {isExpanded && onCollapse && (
                <span title="Collapse node" className="absolute top-2 right-2 z-10">
                    <Minimize2
                        className="h-3.5 w-3.5 text-(--color-info-w70) dark:text-(--color-info-wMain) opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer hover:text-(--color-info-wMain) dark:hover:text-(--color-info-w30)"
                        onClick={(e) => {
                            e.stopPropagation();
                            onCollapse(node.id);
                        }}
                    />
                </span>
            )}
            {/* Expand icon - top right, only show on hover when collapsed */}
            {isCollapsed && onExpand && (
                <span title="Expand node" className="absolute top-2 right-2 z-10">
                    <Maximize2
                        className="h-3.5 w-3.5 text-(--color-info-w70) dark:text-(--color-info-wMain) opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer hover:text-(--color-info-wMain) dark:hover:text-(--color-info-w30)"
                        onClick={(e) => {
                            e.stopPropagation();
                            onExpand(node.id);
                        }}
                    />
                </span>
            )}
            {/* Header */}
            <div
                className={`cursor-pointer bg-(--color-info-w10) pl-4 pr-8 py-3 dark:bg-(--color-secondary-w70) ${
                    node.children.length === 0 && (!node.parallelBranches || node.parallelBranches.length === 0)
                        ? 'rounded-md'  // No content below, round all corners
                        : 'rounded-t-md'  // Content below, round only top
                }`}
                onClick={(e) => {
                    e.stopPropagation();
                    onClick?.(node);
                }}
                title={node.data.description}
            >
                <div className="flex items-center justify-center gap-2">
                    <Bot className="h-4 w-4 flex-shrink-0 text-(--color-info-wMain) dark:text-(--color-info-w70)" />
                    <div className="text-sm font-semibold text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10) truncate">
                        {node.data.label}
                    </div>
                </div>
            </div>

            {/* Content - Children with inline connectors */}
            {node.children.length > 0 && (
                <div className={`p-4 flex flex-col items-center ${!node.parallelBranches || node.parallelBranches.length === 0 ? 'rounded-b-md' : ''}`}>
                    {node.children.map((child, index) => (
                        <Fragment key={child.id}>
                            {renderChild(child)}
                            {/* Connector line to next child */}
                            {index < node.children.length - 1 && (
                                <div className="w-0.5 h-4 bg-(--color-secondary-w40) dark:bg-(--color-secondary-w70) my-0" />
                            )}
                        </Fragment>
                    ))}
                </div>
            )}

            {/* Parallel Branches */}
            {node.parallelBranches && node.parallelBranches.length > 0 && (
                <div className="p-4 border-t-2 border-(--color-info-w30) dark:border-(--color-info-w100) rounded-b-md">
                    <div className="grid gap-4" style={{ gridAutoFlow: 'column', gridAutoColumns: '1fr' }}>
                        {node.parallelBranches.map((branch, branchIndex) => (
                            <div key={branchIndex} className="flex flex-col items-center">
                                {branch.map((child, index) => (
                                    <Fragment key={child.id}>
                                        {renderChild(child)}
                                        {/* Connector line to next child in branch */}
                                        {index < branch.length - 1 && (
                                            <div className="w-0.5 h-4 bg-(--color-secondary-w40) dark:bg-(--color-secondary-w70) my-0" />
                                        )}
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
