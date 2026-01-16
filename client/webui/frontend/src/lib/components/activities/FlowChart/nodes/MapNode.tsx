import { Fragment, useMemo, type FC } from "react";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/lib/components/ui";
import type { LayoutNode } from "../utils/types";
import AgentNode from "./AgentNode";

interface MapNodeProps {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
    onChildClick?: (child: LayoutNode) => void;
    onExpand?: (nodeId: string) => void;
    onCollapse?: (nodeId: string) => void;
}

const MapNode: FC<MapNodeProps> = ({ node, isSelected, onClick, onChildClick, onExpand, onCollapse }) => {
    const getStatusColor = () => {
        switch (node.data.status) {
            case "completed":
                return "bg-(--color-accent-n1-w10) border-(--color-accent-n1-wMain) dark:bg-(--color-accent-n1-w100)/30 dark:border-(--color-accent-n1-wMain)";
            case "in-progress":
                return "bg-(--color-info-w10) border-(--color-info-wMain) dark:bg-(--color-info-w100)/30 dark:border-(--color-info-wMain)";
            case "error":
                return "bg-(--color-error-w10) border-(--color-error-wMain) dark:bg-(--color-error-w100)/30 dark:border-(--color-error-wMain)";
            default:
                return "bg-(--color-secondary-w10) border-(--color-secondary-w40) dark:bg-(--color-background-wMain) dark:border-(--color-secondary-w70)";
        }
    };

    // Group children by iterationIndex to create branches
    const branches = useMemo(() => {
        const branchMap = new Map<number, typeof node.children>();
        for (const child of node.children) {
            const iterationIndex = child.data.iterationIndex ?? 0;
            if (!branchMap.has(iterationIndex)) {
                branchMap.set(iterationIndex, []);
            }
            branchMap.get(iterationIndex)!.push(child);
        }
        // Sort by iteration index and return as array of arrays
        return Array.from(branchMap.entries())
            .sort((a, b) => a[0] - b[0])
            .map(([, children]) => children);
    }, [node]);

    const hasChildren = branches.length > 0;
    const label = 'Map';
    const colorClass = "border-(--color-accent-n1-w30) bg-(--color-accent-n1-w10)/30 dark:border-(--color-accent-n1-wMain) dark:bg-(--color-accent-n1-w100)/20";
    const labelColorClass = "text-(--color-accent-n1-wMain) dark:text-(--color-accent-n1-w60) border-(--color-accent-n1-w30) dark:border-(--color-accent-n1-w100) hover:bg-(--color-accent-n1-w10) dark:hover:bg-(--color-accent-n1-w100)/50";
    const connectorColor = "bg-(--color-accent-n1-w30) dark:bg-(--color-accent-n1-wMain)";

    // Render a child node (iterations are agent nodes)
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
                return null;
        }
    };

    // If the node has children, render as a container with parallel branches
    if (hasChildren) {
        return (
            <div
                className={`relative rounded-lg border-2 border-dashed ${colorClass} ${
                    isSelected ? "ring-2 ring-blue-500" : ""
                }`}
                style={{
                    minWidth: "200px",
                    position: "relative",
                }}
            >
                {/* Label with icon - clickable */}
                <Tooltip>
                    <TooltipTrigger asChild>
                        <div
                            className={`absolute -top-3 left-4 px-2 text-xs font-bold bg-(--color-secondary-w10) dark:bg-(--color-background-w100) rounded-md border flex items-center gap-1.5 cursor-pointer transition-colors ${labelColorClass}`}
                            onClick={(e) => {
                                e.stopPropagation();
                                onClick?.(node);
                            }}
                        >
                            {/* Parallel/Branch Icon */}
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
                                    d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"
                                />
                            </svg>
                            {node.data.label || label}
                        </div>
                    </TooltipTrigger>
                    <TooltipContent>{`${label}: ${branches.length} parallel branches`}</TooltipContent>
                </Tooltip>

                {/* Parallel branches displayed side-by-side */}
                <div className="p-4 pt-3 flex flex-row items-start gap-4">
                    {branches.map((branch, branchIndex) => (
                        <div key={`branch-${branchIndex}`} className="flex flex-col items-center">
                            {/* Branch children */}
                            {branch.map((child, childIndex) => (
                                <Fragment key={child.id}>
                                    {renderChild(child)}
                                    {/* Connector line to next child in same branch */}
                                    {childIndex < branch.length - 1 && (
                                        <div className={`w-0.5 h-4 ${connectorColor} my-1`} />
                                    )}
                                </Fragment>
                            ))}
                        </div>
                    ))}
                </div>
            </div>
        );
    }

    // No parallel branches yet - render as compact badge
    const badgeTooltip = node.data.description || `Map: Waiting for items...`;

    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <div
                    className="relative flex items-center justify-center cursor-pointer"
                    style={{ width: `${node.width}px`, height: `${node.height}px` }}
                    onClick={(e) => {
                        e.stopPropagation();
                        onClick?.(node);
                    }}
                >
                    {/* Stadium/Pill shape */}
                    <div
                        className={`relative w-20 h-10 rounded-full border-2 shadow-sm transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-md flex items-center justify-center ${getStatusColor()} ${
                            isSelected ? "ring-2 ring-blue-500" : ""
                        }`}
                    >
                        {/* Parallel Icon */}
                        <svg
                            className="absolute -top-1 -right-1 w-4 h-4 text-(--color-accent-n1-wMain) dark:text-(--color-accent-n1-w60)"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"
                            />
                        </svg>

                        {/* Content */}
                        <div className="flex flex-col items-center justify-center text-center pointer-events-none">
                            <div className="text-[10px] font-bold text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10)">
                                {node.data.label || label}
                            </div>
                        </div>
                    </div>
                </div>
            </TooltipTrigger>
            <TooltipContent>{badgeTooltip}</TooltipContent>
        </Tooltip>
    );
};

export default MapNode;
