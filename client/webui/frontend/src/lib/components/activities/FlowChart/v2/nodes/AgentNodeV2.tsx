import React from "react";
import { Bot } from "lucide-react";
import type { LayoutNode } from "../utils/types";
import LLMNodeV2 from "./LLMNodeV2";
import ToolNodeV2 from "./ToolNodeV2";
import ConditionalNodeV2 from "./ConditionalNodeV2";
import WorkflowGroupV2 from "./WorkflowGroupV2";

interface AgentNodeV2Props {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
    onChildClick?: (child: LayoutNode) => void;
}

const AgentNodeV2: React.FC<AgentNodeV2Props> = ({ node, isSelected, onClick, onChildClick }) => {
    // Pill variant for Start/Finish/Join nodes
    if (node.data.variant === 'pill') {
        const opacityClass = node.data.isSkipped ? "opacity-50" : "";
        const borderStyleClass = node.data.isSkipped ? "border-dashed" : "border-solid";

        return (
            <div
                className={`cursor-pointer rounded-full border-2 border-indigo-500 bg-indigo-50 px-4 py-2 text-indigo-900 shadow-sm transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-md dark:border-indigo-400 dark:bg-indigo-900/50 dark:text-indigo-100 ${opacityClass} ${borderStyleClass} ${
                    isSelected ? "ring-2 ring-blue-500" : ""
                }`}
                style={{
                    width: `${node.width}px`,
                    minWidth: "80px",
                    textAlign: "center",
                }}
                onClick={() => onClick?.(node)}
                title={node.data.description}
            >
                <div className="flex items-center justify-center">
                    <div className="text-sm font-bold">{node.data.label}</div>
                </div>
            </div>
        );
    }

    // Regular agent node with children
    const opacityClass = node.data.isSkipped ? "opacity-50" : "";
    const borderStyleClass = node.data.isSkipped ? "border-dashed" : "border-solid";

    // Render a child node recursively
    const renderChild = (child: LayoutNode) => {
        const childProps = {
            node: child,
            onClick: onChildClick,
        };

        switch (child.type) {
            case 'agent':
                // Recursive!
                return <AgentNodeV2 key={child.id} {...childProps} onChildClick={onChildClick} />;
            case 'llm':
                return <LLMNodeV2 key={child.id} {...childProps} />;
            case 'tool':
                return <ToolNodeV2 key={child.id} {...childProps} />;
            case 'conditional':
                return <ConditionalNodeV2 key={child.id} {...childProps} />;
            case 'group':
                return <WorkflowGroupV2 key={child.id} {...childProps} onChildClick={onChildClick} />;
            default:
                return null;
        }
    };

    return (
        <div
            className={`rounded-md border-2 border-blue-700 bg-white shadow-md transition-all duration-200 ease-in-out hover:shadow-xl dark:border-blue-600 dark:bg-gray-800 ${opacityClass} ${borderStyleClass} ${
                isSelected ? "ring-2 ring-blue-500" : ""
            }`}
            style={{
                width: `${node.width}px`,
                minWidth: "180px",
            }}
        >
            {/* Header */}
            <div
                className={`cursor-pointer bg-blue-50 px-4 py-3 dark:bg-gray-700 ${
                    node.children.length === 0 && (!node.parallelBranches || node.parallelBranches.length === 0)
                        ? 'rounded-md'  // No content below, round all corners
                        : 'rounded-t-md'  // Content below, round only top
                }`}
                onClick={() => onClick?.(node)}
                title={node.data.description}
            >
                <div className="flex items-center justify-center gap-2">
                    <Bot className="h-4 w-4 flex-shrink-0 text-blue-600 dark:text-blue-400" />
                    <div className="text-sm font-semibold text-gray-800 dark:text-gray-200 truncate">
                        {node.data.label}
                    </div>
                </div>
            </div>

            {/* Content - Children with inline connectors */}
            {node.children.length > 0 && (
                <div className={`p-4 flex flex-col items-center ${!node.parallelBranches || node.parallelBranches.length === 0 ? 'rounded-b-md' : ''}`}>
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
            )}

            {/* Parallel Branches */}
            {node.parallelBranches && node.parallelBranches.length > 0 && (
                <div className="p-4 border-t-2 border-blue-200 dark:border-blue-800 rounded-b-md">
                    <div className="flex gap-4">
                        {node.parallelBranches.map((branch, branchIndex) => (
                            <div key={branchIndex} className="flex flex-col gap-4 flex-1">
                                {branch.map(renderChild)}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default AgentNodeV2;
