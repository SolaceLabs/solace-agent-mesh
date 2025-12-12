import React from "react";
import { Workflow, Maximize2, Minimize2 } from "lucide-react";
import type { LayoutNode } from "../utils/types";
import AgentNodeV2 from "./AgentNodeV2";
import ConditionalNodeV2 from "./ConditionalNodeV2";

interface WorkflowGroupV2Props {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
    onChildClick?: (child: LayoutNode) => void;
    onExpand?: (nodeId: string) => void;
    onCollapse?: (nodeId: string) => void;
}

const WorkflowGroupV2: React.FC<WorkflowGroupV2Props> = ({ node, isSelected, onClick, onChildClick, onExpand, onCollapse }) => {
    const isCollapsed = node.data.isCollapsed;
    const isExpanded = node.data.isExpanded;
    const isProcessing = node.data.hasProcessingChildren;
    const haloClass = isProcessing ? 'processing-halo' : '';

    // Render a child node
    const renderChild = (child: LayoutNode) => {
        const childProps = {
            node: child,
            onClick: onChildClick,
            onExpand,
            onCollapse,
        };

        switch (child.type) {
            case 'agent':
                return <AgentNodeV2 key={child.id} {...childProps} onChildClick={onChildClick} />;
            case 'conditional':
                return <ConditionalNodeV2 key={child.id} {...childProps} />;
            default:
                return null;
        }
    };

    // Collapsed view - similar to collapsed agent but with workflow styling
    if (isCollapsed) {
        return (
            <div
                className={`group relative rounded-md border-2 border-dashed border-purple-500 bg-white shadow-md transition-all duration-200 ease-in-out hover:shadow-xl dark:border-purple-400 dark:bg-gray-800 ${
                    isSelected ? "ring-2 ring-blue-500" : ""
                } ${haloClass}`}
                style={{
                    minWidth: "180px",
                }}
            >
                {/* Expand icon - top right, only show on hover */}
                {onExpand && (
                    <span title="Expand workflow" className="absolute top-2 right-2 z-10">
                        <Maximize2
                            className="h-3.5 w-3.5 text-purple-400 dark:text-purple-500 opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer hover:text-purple-600 dark:hover:text-purple-300"
                            onClick={(e) => {
                                e.stopPropagation();
                                onExpand(node.id);
                            }}
                        />
                    </span>
                )}
                {/* Header */}
                <div
                    className="cursor-pointer bg-purple-50 px-4 py-3 dark:bg-gray-700 rounded-md"
                    onClick={(e) => {
                        e.stopPropagation();
                        onClick?.(node);
                    }}
                    title={node.data.description || "Click to view workflow details"}
                >
                    <div className="flex items-center justify-center gap-2">
                        <Workflow className="h-4 w-4 flex-shrink-0 text-purple-600 dark:text-purple-400" />
                        <div className="text-sm font-semibold text-gray-800 dark:text-gray-200 truncate">
                            {node.data.label}
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    // Full expanded view
    return (
        <div
            className={`group rounded-lg border-2 border-dashed border-gray-400 bg-gray-50/50 dark:border-gray-600 dark:bg-gray-900/50 ${
                isSelected ? "ring-2 ring-blue-500" : ""
            }`}
            style={{
                minWidth: "200px",
                position: "relative",
            }}
        >
            {/* Collapse icon - top right, only show on hover when expanded */}
            {isExpanded && onCollapse && (
                <span title="Collapse workflow" className="absolute top-2 right-2 z-10">
                    <Minimize2
                        className="h-3.5 w-3.5 text-purple-400 dark:text-purple-500 opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer hover:text-purple-600 dark:hover:text-purple-300"
                        onClick={(e) => {
                            e.stopPropagation();
                            onCollapse(node.id);
                        }}
                    />
                </span>
            )}
            {/* Label - clickable */}
            {node.data.label && (
                <div
                    className="absolute -top-3 left-4 px-2 text-xs font-bold text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-900 rounded-md border border-gray-200 dark:border-gray-700 flex items-center gap-1.5 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                    onClick={(e) => {
                        e.stopPropagation();
                        onClick?.(node);
                    }}
                    title="Click to view workflow details"
                >
                    <Workflow className="h-3 w-3 flex-shrink-0" />
                    {node.data.label}
                </div>
            )}

            {/* Children with inline connectors */}
            <div className="p-6 flex flex-col items-center">
                {node.children.map((child, index) => (
                    <React.Fragment key={child.id}>
                        {renderChild(child)}
                        {/* Connector line to next child */}
                        {index < node.children.length - 1 && (
                            <div className="w-0.5 h-4 bg-gray-400 dark:bg-gray-600 my-0" />
                        )}
                    </React.Fragment>
                ))}
            </div>
        </div>
    );
};

export default WorkflowGroupV2;
