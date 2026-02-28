import { type ReactNode, Fragment, useRef, useState, useLayoutEffect, useEffect, useCallback } from "react";
import { Workflow, Maximize2, Minimize2 } from "lucide-react";

import { Button } from "@/lib/components/ui";

import type { LayoutNode } from "../utils/types";
import { ACTIVITY_NODE_BASE_STYLES, ACTIVITY_NODE_SELECTED_CLASS, ACTIVITY_NODE_PROCESSING_CLASS, ACTIVITY_NODE_LAYOUT, CONNECTOR_LINE_CLASSES, CONNECTOR_SIZES } from "../utils/nodeStyles";
import AgentNode from "./AgentNode";
import SwitchNode from "./SwitchNode";
import LoopNode from "./LoopNode";
import MapNode from "./MapNode";

interface WorkflowGroupProps {
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
 * The curve uses a constant control offset at the source for a consistent departure curve,
 * and a scaled control offset at the target to create long vertical sections for longer distances.
 *
 * @param scale - The current zoom scale factor (to convert screen coordinates to SVG coordinates)
 */
function generateBezierPath(sourceRect: DOMRect, targetRect: DOMRect, containerRect: DOMRect, scale: number = 1): string {
    // Source: bottom center of the source element
    // Divide by scale to convert from screen coordinates (affected by zoom) to SVG coordinates
    const x1 = (sourceRect.left + sourceRect.width / 2 - containerRect.left) / scale;
    const y1 = (sourceRect.bottom - containerRect.top) / scale;

    // Target: top center of the target element
    const x2 = (targetRect.left + targetRect.width / 2 - containerRect.left) / scale;
    const y2 = (targetRect.top - containerRect.top) / scale;

    // Control points for a curve with vertical start and end
    const verticalDistance = Math.abs(y2 - y1);

    // Target control point: constant offset for consistent curve at arrival
    const targetControlOffset = 40;

    // Source control point: extends far down to create a very long vertical section
    // Using 90% of the distance creates an almost straight drop from the source
    const sourceControlOffset = Math.max(verticalDistance * 1.0, 40);

    // Control point 1: directly below source (same x) for vertical start
    const cx1 = x1;
    const cy1 = y1 + sourceControlOffset;

    // Control point 2: directly above target (same x) for vertical end
    const cx2 = x2;
    const cy2 = y2 - targetControlOffset;

    return `M ${x1},${y1} C ${cx1},${cy1} ${cx2},${cy2} ${x2},${y2}`;
}

const WorkflowGroup = ({ node, isSelected, onClick, onChildClick, onExpand, onCollapse }: WorkflowGroupProps) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [bezierPaths, setBezierPaths] = useState<BezierPath[]>([]);
    const [resizeCounter, setResizeCounter] = useState(0);

    const isCollapsed = node.data.isCollapsed;
    const isExpanded = node.data.isExpanded;
    const isProcessing = node.data.hasProcessingChildren;
    const haloClass = isProcessing ? ACTIVITY_NODE_PROCESSING_CLASS : "";

    // Layout constants - match AgentNode for consistency
    const WORKFLOW_WIDTH = ACTIVITY_NODE_LAYOUT.CONTAINER_WIDTH;
    const HEADER_HEIGHT = ACTIVITY_NODE_LAYOUT.HEADER_HEIGHT;

    // Function to calculate bezier paths
    const calculateBezierPaths = useCallback(() => {
        if (!containerRef.current || isCollapsed) {
            setBezierPaths([]);
            return;
        }

        const container = containerRef.current;
        const containerRect = container.getBoundingClientRect();

        // Calculate the current zoom scale by comparing the visual size (getBoundingClientRect)
        // with the actual size (offsetWidth). When zoomed, the visual size changes but offsetWidth stays the same.
        const scale = containerRect.width / container.offsetWidth;

        const paths: BezierPath[] = [];

        // Find all parallel blocks and their preceding/following nodes
        const parallelBlocks = container.querySelectorAll("[data-parallel-block]");

        parallelBlocks.forEach(blockEl => {
            const blockId = blockEl.getAttribute("data-parallel-block");
            const precedingNodeId = blockEl.getAttribute("data-preceding-node");
            const followingNodeId = blockEl.getAttribute("data-following-node");

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
                        const pathD = generateBezierPath(precedingRect, targetRect, containerRect, scale);

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
                        const pathD = generateBezierPath(sourceRect, followingRect, containerRect, scale);

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
        const nodes = containerRef.current.querySelectorAll("[data-node-id]");
        nodes.forEach(node => resizeObserver.observe(node));

        return () => resizeObserver.disconnect();
    }, [node.children, isCollapsed]);

    // Use MutationObserver to detect zoom/pan changes from react-zoom-pan-pinch
    // The transform is applied to ancestor elements, so we watch for style changes
    useEffect(() => {
        if (!containerRef.current || isCollapsed) return;

        // Find the TransformComponent wrapper by looking for an ancestor with transform style
        let transformedParent: Element | null = containerRef.current.parentElement;
        while (transformedParent && !transformedParent.hasAttribute("style")) {
            transformedParent = transformedParent.parentElement;
        }

        if (!transformedParent) return;

        const mutationObserver = new MutationObserver(mutations => {
            // Check if any mutation is a style change (which includes transform changes)
            const hasStyleChange = mutations.some(m => m.attributeName === "style");
            if (hasStyleChange) {
                setResizeCounter(c => c + 1);
            }
        });

        // Observe style attribute changes on the transformed parent and its ancestors
        // (react-zoom-pan-pinch may apply transforms at different levels)
        let current: Element | null = transformedParent;
        while (current && current !== document.body) {
            mutationObserver.observe(current, { attributes: true, attributeFilter: ["style"] });
            current = current.parentElement;
        }

        return () => mutationObserver.disconnect();
    }, [isCollapsed]);

    // Render a child node with data attributes for connector calculation
    const renderChild = useCallback(
        (child: LayoutNode, precedingNodeId?: string, followingNodeId?: string): ReactNode => {
            const childProps = {
                node: child,
                onClick: onChildClick,
                onExpand,
                onCollapse,
            };

            switch (child.type) {
                case "agent":
                    return (
                        <div key={child.id} data-node-id={child.id}>
                            <AgentNode {...childProps} onChildClick={onChildClick} />
                        </div>
                    );
                case "switch":
                    return (
                        <div key={child.id} data-node-id={child.id}>
                            <SwitchNode {...childProps} />
                        </div>
                    );
                case "loop":
                    return (
                        <div key={child.id} data-node-id={child.id}>
                            <LoopNode {...childProps} onChildClick={onChildClick} />
                        </div>
                    );
                case "map":
                    return (
                        <div key={child.id} data-node-id={child.id}>
                            <MapNode {...childProps} onChildClick={onChildClick} />
                        </div>
                    );
                case "group":
                    // Nested workflow group - render recursively
                    return (
                        <div key={child.id} data-node-id={child.id}>
                            <WorkflowGroup {...childProps} onChildClick={onChildClick} />
                        </div>
                    );
                case "parallelBlock": {
                    // Don't render empty parallel blocks
                    if (child.children.length === 0) {
                        return null;
                    }
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
                        <div key={child.id} data-parallel-block={child.id} data-preceding-node={precedingNodeId} data-following-node={followingNodeId} className="my-12 flex flex-row items-start gap-4">
                            {sortedBranches.map(([branchIdx, branchChildren]) => (
                                <div key={`branch-${branchIdx}`} className="flex flex-col items-center gap-2">
                                    {branchChildren.map((branchChild, nodeIdx) => (
                                        <Fragment key={branchChild.id}>
                                            <div data-node-id={branchChild.id} data-branch-start={nodeIdx === 0 ? "true" : undefined} data-branch-end={nodeIdx === branchChildren.length - 1 ? "true" : undefined}>
                                                {renderChild(branchChild)}
                                            </div>
                                            {/* Connector line to next node in branch */}
                                            {nodeIdx < branchChildren.length - 1 && <div className={`${CONNECTOR_SIZES.BRANCH} ${CONNECTOR_LINE_CLASSES}`} />}
                                        </Fragment>
                                    ))}
                                </div>
                            ))}
                        </div>
                    );
                }
                default:
                    return null;
            }
        },
        [onChildClick, onExpand, onCollapse]
    );

    // Collapsed view
    if (isCollapsed) {
        return (
            <div
                className={`${ACTIVITY_NODE_BASE_STYLES.RECTANGULAR} ${isSelected ? ACTIVITY_NODE_SELECTED_CLASS : ""} ${haloClass}`}
                style={{
                    width: `${WORKFLOW_WIDTH}px`,
                }}
                onClick={e => {
                    e.stopPropagation();
                    onClick?.(node);
                }}
            >
                <div className="flex min-w-0 items-center gap-2">
                    <Workflow className="h-4 w-4 flex-shrink-0 text-(--color-brand-wMain)" />
                    <div className="truncate text-sm font-semibold">{node.data.label}</div>
                </div>
                {/* Expand control */}
                {onExpand && (
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

    // Full expanded view with straddling header
    return (
        <div className={`flex flex-col px-4 ${haloClass}`} style={{ minWidth: `${WORKFLOW_WIDTH + 72}px` }}>
            {/* Solid Header Box - positioned at top, centered with fixed width */}
            <div
                className={`${ACTIVITY_NODE_BASE_STYLES.CONTAINER_HEADER} ${isSelected ? ACTIVITY_NODE_SELECTED_CLASS : ""} z-20`}
                style={{ width: `${WORKFLOW_WIDTH}px` }}
                onClick={e => {
                    e.stopPropagation();
                    onClick?.(node);
                }}
            >
                <div className="flex items-center justify-between gap-4 px-4 py-2">
                    <div className="flex min-w-0 items-center gap-2">
                        <Workflow className="h-4 w-4 flex-shrink-0 text-(--color-brand-wMain)" />
                        <div className="truncate text-sm font-semibold">{node.data.label}</div>
                    </div>

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
            </div>

            {/* Dotted Children Container - grows with content, extends 16px beyond header on each side */}
            {/* Dark mode background colour should be removed once the stateLayer-w10 is mapped to its correct dark mode value. */}
            <div
                ref={containerRef}
                className="relative rounded border-2 border-dashed border-(--color-secondary-w40) bg-(--color-stateLayer-w10) dark:border-(--color-secondary-w70) dark:bg-[#FFFFFF1a]"
                style={{ marginTop: `-${HEADER_HEIGHT / 2}px`, paddingTop: `${HEADER_HEIGHT / 2 + 16}px` }}
            >
                {/* SVG overlay for bezier connectors */}
                {bezierPaths.length > 0 && (
                    <svg className="pointer-events-none absolute inset-0 z-10" style={{ width: "100%", height: "100%", overflow: "visible" }}>
                        {bezierPaths.map(path => (
                            <path key={path.id} d={path.d} strokeWidth={2} fill="none" className="stroke-(--color-stateLayer-w20) dark:stroke-[#FFFFFF2a]" />
                        ))}
                    </svg>
                )}

                {/* Children with inline connectors */}
                <div className="flex flex-col items-center px-3 pb-4">
                    {node.children.map((child, index) => {
                        // Track the preceding and following nodes for parallel blocks
                        const precedingNode = index > 0 ? node.children[index - 1] : null;
                        const precedingNodeId = precedingNode?.id;
                        const followingNode = index < node.children.length - 1 ? node.children[index + 1] : null;
                        const followingNodeId = followingNode?.id;

                        return (
                            <Fragment key={child.id}>
                                {renderChild(child, precedingNodeId, followingNodeId)}
                                {/* Connector line to next child (only if current is not parallelBlock and next is not parallelBlock) */}
                                {index < node.children.length - 1 && child.type !== "parallelBlock" && node.children[index + 1].type !== "parallelBlock" && <div className="my-0 h-4 w-0.5 bg-(--color-stateLayer-w20) dark:bg-[#FFFFFF2a]" />}
                            </Fragment>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};

export default WorkflowGroup;
