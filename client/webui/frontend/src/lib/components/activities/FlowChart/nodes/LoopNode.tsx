import { Fragment, type FC } from "react";
import type { LayoutNode } from "../utils/types";
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
    const getStatusColor = () => {
        switch (node.data.status) {
            case "completed":
                return "bg-teal-100 border-teal-500 dark:bg-teal-900/30 dark:border-teal-500";
            case "in-progress":
                return "bg-blue-100 border-blue-500 dark:bg-blue-900/30 dark:border-blue-500";
            case "error":
                return "bg-red-100 border-red-500 dark:bg-red-900/30 dark:border-red-500";
            default:
                return "bg-gray-100 border-gray-400 dark:bg-gray-800 dark:border-gray-600";
        }
    };

    const currentIteration = node.data.currentIteration ?? 0;
    const maxIterations = node.data.maxIterations ?? 100;
    const hasChildren = node.children && node.children.length > 0;

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

    // If the loop has children (iterations), render as a container
    if (hasChildren) {
        return (
            <div
                className={`relative rounded-lg border-2 border-dashed border-teal-400 bg-teal-50/30 dark:border-teal-600 dark:bg-teal-900/20 ${isSelected ? "ring-2 ring-blue-500" : ""}`}
                style={{
                    minWidth: "200px",
                    position: "relative",
                }}
            >
                {/* Loop Label with icon - clickable */}
                <div
                    className="absolute -top-3 left-4 flex cursor-pointer items-center gap-1.5 rounded-md border border-teal-300 bg-gray-50 px-2 text-xs font-bold text-teal-600 transition-colors hover:bg-teal-50 dark:border-teal-700 dark:bg-gray-900 dark:text-teal-400 dark:hover:bg-teal-900/50"
                    onClick={e => {
                        e.stopPropagation();
                        onClick?.(node);
                    }}
                    title={`Loop: ${node.data.condition || "while condition"} (max ${maxIterations})`}
                >
                    {/* Loop Arrow Icon */}
                    <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    {node.data.label}
                </div>

                {/* Children (loop iterations) with inline connectors */}
                <div className="flex flex-col items-center p-4 pt-3">
                    {node.children.map((child, index) => (
                        <Fragment key={child.id}>
                            {/* Iteration label */}
                            <div className="mb-1 text-[10px] font-medium text-teal-600 dark:text-teal-400">Iteration {index + 1}</div>
                            {renderChild(child)}
                            {/* Connector line to next child */}
                            {index < node.children.length - 1 && <div className="my-1 h-4 w-0.5 bg-teal-400 dark:bg-teal-600" />}
                        </Fragment>
                    ))}
                </div>
            </div>
        );
    }

    // No children yet - render as compact badge
    return (
        <div
            className="relative flex cursor-pointer items-center justify-center"
            style={{ width: `${node.width}px`, height: `${node.height}px` }}
            onClick={e => {
                e.stopPropagation();
                onClick?.(node);
            }}
            title={node.data.description || `Loop: ${node.data.condition || "while condition"} (max ${maxIterations})`}
        >
            {/* Stadium/Pill shape with loop indicator */}
            <div
                className={`relative flex h-10 w-20 items-center justify-center rounded-full border-2 shadow-sm transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-md ${getStatusColor()} ${isSelected ? "ring-2 ring-blue-500" : ""}`}
            >
                {/* Loop Arrow Icon */}
                <svg className="absolute -top-1 -right-1 h-4 w-4 text-teal-600 dark:text-teal-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>

                {/* Content */}
                <div className="pointer-events-none flex flex-col items-center justify-center text-center">
                    <div className="text-[10px] font-bold text-gray-800 dark:text-gray-200">{node.data.label}</div>
                </div>
            </div>

            {/* Iteration Counter (if in progress) */}
            {node.data.status === "in-progress" && currentIteration > 0 && (
                <div className="absolute bottom-[-18px] left-1/2 -translate-x-1/2 transform rounded bg-white/80 px-1.5 py-0.5 text-[9px] font-medium text-gray-600 dark:bg-gray-900/80 dark:text-gray-300">Iteration {currentIteration}</div>
            )}
        </div>
    );
};

export default LoopNode;
