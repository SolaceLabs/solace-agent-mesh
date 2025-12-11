import React from "react";
import type { LayoutNode } from "../utils/types";
import AgentNodeV2 from "./AgentNodeV2";
import ConditionalNodeV2 from "./ConditionalNodeV2";

interface WorkflowGroupV2Props {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
    onChildClick?: (child: LayoutNode) => void;
}

const WorkflowGroupV2: React.FC<WorkflowGroupV2Props> = ({ node, isSelected, onClick, onChildClick }) => {
    // Render a child node
    const renderChild = (child: LayoutNode) => {
        const childProps = {
            node: child,
            onClick: onChildClick,
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

    return (
        <div
            className={`rounded-lg border-2 border-dashed border-gray-400 bg-gray-50/50 dark:border-gray-600 dark:bg-gray-900/50 ${
                isSelected ? "ring-2 ring-blue-500" : ""
            }`}
            style={{
                width: `${node.width}px`,
                position: "relative",
            }}
            onClick={() => onClick?.(node)}
        >
            {/* Label */}
            {node.data.label && (
                <div className="absolute -top-3 left-4 px-2 text-xs font-bold text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-900 rounded-md border border-gray-200 dark:border-gray-700">
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
