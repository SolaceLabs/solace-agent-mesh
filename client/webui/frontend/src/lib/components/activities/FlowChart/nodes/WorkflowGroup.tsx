import React, { useRef, useState, useLayoutEffect, useEffect, useCallback } from "react";
import { Workflow, Maximize2, Minimize2 } from "lucide-react";
import type { LayoutNode } from "../utils/types";
import AgentNodeV2 from "./AgentNodeV2";
import ConditionalNodeV2 from "./ConditionalNodeV2";
import SwitchNodeV2 from "./SwitchNodeV2";
import LoopNodeV2 from "./LoopNodeV2";
import MapNodeV2 from "./MapNodeV2";

interface WorkflowGroupV2Props {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
    onChildClick?: (child: LayoutNode) => void;
    onExpand?: (nodeId: string) => void;
    onCollapse?: (nodeId: string) => void;
}

interface BezierPath {
    id: string;
    d: string;
}

/**
 * Generate a cubic bezier path from source bottom-center to target top-center
 * The curve starts going straight down and ends going straight up for clean vertical transitions
 */
function generateBezierPath(
    sourceRect: DOMRect,
    targetRect: DOMRect,
    containerRect: DOMRect
): string {
    // Source: bottom center of the source element
    const x1 = sourceRect.left + sourceRect.width / 2 - containerRect.left;
    const y1 = sourceRect.bottom - containerRect.top;

    // Target: top center of the target element
    const x2 = targetRect.left + targetRect.width / 2 - containerRect.left;
    const y2 = targetRect.top - containerRect.top;

    // Control points for a curve with vertical start and end
    const verticalDistance = Math.abs(y2 - y1);
    // Use a larger offset to create longer vertical sections
    const controlOffset = Math.max(verticalDistance * 0.4, 40);

    // Control point 1: directly below source (same x) for vertical start
    const cx1 = x1;
    const cy1 = y1 + controlOffset;

    // Control point 2: directly above target (same x) for vertical end
    const cx2 = x2;
    const cy2 = y2 - controlOffset;

    return `M ${x1},${y1} C ${cx1},${cy1} ${cx2},${cy2} ${x2},${y2}`;
}

const WorkflowGroupV2: React.FC<WorkflowGroupV2Props> = ({ node, isSelected, onClick, onChildClick, onExpand, onCollapse }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [bezierPaths, setBezierPaths] = useState<BezierPath[]>([]);
    const [resizeCounter, setResizeCounter] = useState(0);

    const isCollapsed = node.data.isCollapsed;
    const isExpanded = node.data.isExpanded;
    const isProcessing = node.data.hasProcessingChildren;
    const haloClass = isProcessing ? 'processing-halo' : '';

    // Function to calculate bezier paths
    const calculateBezierPaths = useCallback(() => {
        if (!containerRef.current || isCollapsed) {
            setBezierPaths([]);
            return;
        }

        const container = containerRef.current;
        const containerRect = container.getBoundingClientRect();

        const paths: BezierPath[] = [];

        // Find all parallel blocks and their preceding/following nodes
        const parallelBlocks = container.querySelectorAll('[data-parallel-block]');

        parallelBlocks.forEach((blockEl) => {
            const blockId = blockEl.getAttribute('data-parallel-block');
            const precedingNodeId = blockEl.getAttribute('data-preceding-node');
            const followingNodeId = blockEl.getAttribute('data-following-node');

            // Draw lines FROM preceding node TO branch starts
            if (precedingNodeId) {
                const precedingWrapper = container.querySelector(`[data-node-id="${precedingNodeId}"]`);
                if (precedingWrapper) {
                    const precedingEl = precedingWrapper.firstElementChild || precedingWrapper;
                    const precedingRect = precedingEl.getBoundingClientRect();

                    const branchStartNodes = blockEl.querySelectorAll('[data-branch-start="true"]');
                    branchStartNodes.forEach((branchStartEl, index) => {
                        const targetEl = branchStartEl.firstElementChild || branchStartEl;
                        const targetRect = targetEl.getBoundingClientRect();
                        const pathD = generateBezierPath(precedingRect, targetRect, containerRect);

                        paths.push({
                            id: `${blockId}-start-${index}`,
                            d: pathD,
                        });
                    });
                }
            }

            // Draw lines FROM branch ends TO following node
            if (followingNodeId) {
                const followingWrapper = container.querySelector(`[data-node-id="${followingNodeId}"]`);
                if (followingWrapper) {
                    const followingEl = followingWrapper.firstElementChild || followingWrapper;
                    const followingRect = followingEl.getBoundingClientRect();

                    const branchEndNodes = blockEl.querySelectorAll('[data-branch-end="true"]');
                    branchEndNodes.forEach((branchEndEl, index) => {
                        const sourceEl = branchEndEl.firstElementChild || branchEndEl;
                        const sourceRect = sourceEl.getBoundingClientRect();
                        const pathD = generateBezierPath(sourceRect, followingRect, containerRect);

                        paths.push({
                            id: `${blockId}-end-${index}`,
                            d: pathD,
                        });
                    });
                }
            }
        });

        setBezierPaths(paths);
    }, [isCollapsed]);

    // Calculate bezier paths after render
    useLayoutEffect(() => {
        calculateBezierPaths();
    }, [node.children, isCollapsed, resizeCounter, calculateBezierPaths]);

    // Use ResizeObserver to detect when children expand/collapse (changes their size)
    useEffect(() => {
        if (!containerRef.current || isCollapsed) return;

        const resizeObserver = new ResizeObserver(() => {
            // Trigger recalculation by incrementing counter
            setResizeCounter(c => c + 1);
        });

        // Observe the container and all nodes within it
        resizeObserver.observe(containerRef.current);
        const nodes = containerRef.current.querySelectorAll('[data-node-id]');
        nodes.forEach(node => resizeObserver.observe(node));

        return () => resizeObserver.disconnect();
    }, [node.children, isCollapsed]);

    // Render a child node with data attributes for connector calculation
    const renderChild = (child: LayoutNode, precedingNodeId?: string, followingNodeId?: string): React.ReactNode => {
        const childProps = {
            node: child,
            onClick: onChildClick,
            onExpand,
            onCollapse,
        };

        switch (child.type) {
            case 'agent':
                return (
                    <div key={child.id} data-node-id={child.id}>
                        <AgentNodeV2 {...childProps} onChildClick={onChildClick} />
                    </div>
                );
            case 'conditional':
                return (
                    <div key={child.id} data-node-id={child.id}>
                        <ConditionalNodeV2 {...childProps} />
                    </div>
                );
            case 'switch':
                return (
                    <div key={child.id} data-node-id={child.id}>
                        <SwitchNodeV2 {...childProps} />
                    </div>
                );
            case 'loop':
                return (
                    <div key={child.id} data-node-id={child.id}>
                        <LoopNodeV2 {...childProps} onChildClick={onChildClick} />
                    </div>
                );
            case 'map':
                return (
                    <div key={child.id} data-node-id={child.id}>
                        <MapNodeV2 {...childProps} onChildClick={onChildClick} />
                    </div>
                );
            case 'parallelBlock': {
                // Group children by iterationIndex (branch index) for proper chain visualization
                const branches = new Map<number, LayoutNode[]>();
                for (const parallelChild of child.children) {
                    const branchIdx = parallelChild.data.iterationIndex ?? 0;
                    if (!branches.has(branchIdx)) {
                        branches.set(branchIdx, []);
                    }
                    branches.get(branchIdx)!.push(parallelChild);
                }

                // Sort branches by index
                const sortedBranches = Array.from(branches.entries()).sort((a, b) => a[0] - b[0]);

                // Render parallel block - branches side-by-side, nodes within each branch stacked vertically
                // Container is invisible - connectors are drawn via SVG bezier paths
                return (
                    <div
                        key={child.id}
                        data-parallel-block={child.id}
                        data-preceding-node={precedingNodeId}
                        data-following-node={followingNodeId}
                        className="flex flex-row items-start gap-4 my-12"
                    >
                        {sortedBranches.map(([branchIdx, branchChildren]) => (
                            <div key={`branch-${branchIdx}`} className="flex flex-col items-center gap-2">
                                {branchChildren.map((branchChild, nodeIdx) => (
                                    <React.Fragment key={branchChild.id}>
                                        <div
                                            data-node-id={branchChild.id}
                                            data-branch-start={nodeIdx === 0 ? "true" : undefined}
                                            data-branch-end={nodeIdx === branchChildren.length - 1 ? "true" : undefined}
                                        >
                                            {renderChild(branchChild)}
                                        </div>
                                        {/* Connector line to next node in branch */}
                                        {nodeIdx < branchChildren.length - 1 && (
                                            <div className="w-0.5 h-3 bg-gray-400 dark:bg-gray-600" />
                                        )}
                                    </React.Fragment>
                                ))}
                            </div>
                        ))}
                    </div>
                );
            }
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
            ref={containerRef}
            className={`group rounded-lg border-2 border-dashed border-gray-400 bg-gray-50/50 dark:border-gray-600 dark:bg-gray-900/50 ${
                isSelected ? "ring-2 ring-blue-500" : ""
            }`}
            style={{
                minWidth: "200px",
                position: "relative",
            }}
        >
            {/* SVG overlay for bezier connectors */}
            {bezierPaths.length > 0 && (
                <svg
                    className="absolute inset-0 pointer-events-none z-10"
                    style={{ width: '100%', height: '100%', overflow: 'visible' }}
                >
                    {bezierPaths.map((path) => (
                        <path
                            key={path.id}
                            d={path.d}
                            stroke="#9CA3AF"
                            strokeWidth={2}
                            fill="none"
                            className="dark:stroke-gray-500"
                        />
                    ))}
                </svg>
            )}

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
                {node.children.map((child, index) => {
                    // Track the preceding and following nodes for parallel blocks
                    const precedingNode = index > 0 ? node.children[index - 1] : null;
                    const precedingNodeId = precedingNode?.id;
                    const followingNode = index < node.children.length - 1 ? node.children[index + 1] : null;
                    const followingNodeId = followingNode?.id;

                    return (
                        <React.Fragment key={child.id}>
                            {renderChild(child, precedingNodeId, followingNodeId)}
                            {/* Connector line to next child (only if current is not parallelBlock and next is not parallelBlock) */}
                            {index < node.children.length - 1 &&
                             child.type !== 'parallelBlock' &&
                             node.children[index + 1].type !== 'parallelBlock' && (
                                <div className="w-0.5 h-4 bg-gray-400 dark:bg-gray-600 my-0" />
                            )}
                        </React.Fragment>
                    );
                })}
            </div>
        </div>
    );
};

export default WorkflowGroupV2;
