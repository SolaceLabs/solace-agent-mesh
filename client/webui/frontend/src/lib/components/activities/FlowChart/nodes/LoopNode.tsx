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
                return "bg-(--color-accent-n2-w10) border-(--color-accent-n2-wMain) dark:bg-(--color-accent-n2-w100)/30 dark:border-(--color-accent-n2-wMain)";
            case "in-progress":
                return "bg-(--color-info-w10) border-(--color-info-wMain) dark:bg-(--color-info-w100)/30 dark:border-(--color-info-wMain)";
            case "error":
                return "bg-(--color-error-w10) border-(--color-error-wMain) dark:bg-(--color-error-w100)/30 dark:border-(--color-error-wMain)";
            default:
                return "bg-(--color-secondary-w10) border-(--color-secondary-w40) dark:bg-(--color-background-wMain) dark:border-(--color-secondary-w70)";
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
            case 'agent':
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
                className={`relative rounded-lg border-2 border-dashed border-(--color-accent-n2-w30) bg-(--color-accent-n2-w10)/30 dark:border-(--color-accent-n2-wMain) dark:bg-(--color-accent-n2-w100)/20 ${
                    isSelected ? "ring-2 ring-blue-500" : ""
                }`}
                style={{
                    minWidth: "200px",
                    position: "relative",
                }}
            >
                {/* Loop Label with icon - clickable */}
                <div
                    className="absolute -top-3 left-4 px-2 text-xs font-bold text-(--color-accent-n2-wMain) dark:text-(--color-accent-n2-w30) bg-(--color-secondary-w10) dark:bg-(--color-background-w100) rounded-md border border-(--color-accent-n2-w30) dark:border-(--color-accent-n2-w100) flex items-center gap-1.5 cursor-pointer hover:bg-(--color-accent-n2-w10) dark:hover:bg-(--color-accent-n2-w100)/50 transition-colors"
                    onClick={(e) => {
                        e.stopPropagation();
                        onClick?.(node);
                    }}
                    title={`Loop: ${node.data.condition || 'while condition'} (max ${maxIterations})`}
                >
                    {/* Loop Arrow Icon */}
                    <svg
                        className="w-3 h-3"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                    >
                        <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                        />
                    </svg>
                    {node.data.label}
                </div>

                {/* Children (loop iterations) with inline connectors */}
                <div className="p-4 pt-3 flex flex-col items-center">
                    {node.children.map((child, index) => (
                        <Fragment key={child.id}>
                            {/* Iteration label */}
                            <div className="text-[10px] font-medium text-(--color-accent-n2-wMain) dark:text-(--color-accent-n2-w30) mb-1">
                                Iteration {index + 1}
                            </div>
                            {renderChild(child)}
                            {/* Connector line to next child */}
                            {index < node.children.length - 1 && (
                                <div className="w-0.5 h-4 bg-(--color-accent-n2-w30) dark:bg-(--color-accent-n2-wMain) my-1" />
                            )}
                        </Fragment>
                    ))}
                </div>
            </div>
        );
    }

    // No children yet - render as compact badge
    return (
        <div
            className="relative flex items-center justify-center cursor-pointer"
            style={{ width: `${node.width}px`, height: `${node.height}px` }}
            onClick={(e) => {
                e.stopPropagation();
                onClick?.(node);
            }}
            title={node.data.description || `Loop: ${node.data.condition || 'while condition'} (max ${maxIterations})`}
        >
            {/* Stadium/Pill shape with loop indicator */}
            <div
                className={`relative w-20 h-10 rounded-full border-2 shadow-sm transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-md flex items-center justify-center ${getStatusColor()} ${
                    isSelected ? "ring-2 ring-blue-500" : ""
                }`}
            >
                {/* Loop Arrow Icon */}
                <svg
                    className="absolute -top-1 -right-1 w-4 h-4 text-(--color-accent-n2-wMain) dark:text-(--color-accent-n2-w30)"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                >
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                    />
                </svg>

                {/* Content */}
                <div className="flex flex-col items-center justify-center text-center pointer-events-none">
                    <div className="text-[10px] font-bold text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10)">
                        {node.data.label}
                    </div>
                </div>
            </div>

            {/* Iteration Counter (if in progress) */}
            {node.data.status === 'in-progress' && currentIteration > 0 && (
                <div className="absolute bottom-[-18px] left-1/2 transform -translate-x-1/2 text-[9px] font-medium text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50) bg-(--color-background-w10)/80 dark:bg-(--color-background-w100)/80 px-1.5 py-0.5 rounded">
                    Iteration {currentIteration}
                </div>
            )}
        </div>
    );
};

export default LoopNode;
