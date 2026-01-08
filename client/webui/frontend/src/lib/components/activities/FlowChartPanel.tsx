import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Background, Controls, MarkerType, Panel, ReactFlow, ReactFlowProvider, useEdgesState, useNodesState, useReactFlow } from "@xyflow/react";
import type { Edge, Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { PopoverManual } from "@/lib/components/ui";
import { useChatContext, useTaskContext } from "@/lib/hooks";
import type { VisualizerStep } from "@/lib/types";
import { getThemeButtonHtmlStyles } from "@/lib/utils";

import { EdgeAnimationService } from "./FlowChart/edgeAnimationService";
import { GROUP_PADDING_X, GROUP_PADDING_Y, NODE_HEIGHT, NODE_WIDTH } from "./FlowChart/taskToFlowData.helpers";
import { transformProcessedStepsToTimelineFlow } from "./FlowChart/taskToFlowData";
import GenericFlowEdge, { type AnimatedEdgeData } from "./FlowChart/customEdges/GenericFlowEdge";
import GenericAgentNode from "./FlowChart/customNodes/GenericAgentNode";
import GenericToolNode from "./FlowChart/customNodes/GenericToolNode";
import LLMNode from "./FlowChart/customNodes/LLMNode";
import OrchestratorAgentNode from "./FlowChart/customNodes/OrchestratorAgentNode";
import UserNode from "./FlowChart/customNodes/UserNode";
import { VisualizerStepCard } from "./VisualizerStepCard";

const nodeTypes = {
    genericAgentNode: GenericAgentNode,
    userNode: UserNode,
    llmNode: LLMNode,
    orchestratorNode: OrchestratorAgentNode,
    genericToolNode: GenericToolNode,
};

const edgeTypes = {
    defaultFlowEdge: GenericFlowEdge,
};

interface FlowChartPanelProps {
    processedSteps: VisualizerStep[];
    isRightPanelVisible?: boolean;
    isSidePanelTransitioning?: boolean;
}

// Stable offset object to prevent unnecessary re-renders
const POPOVER_OFFSET = { x: 16, y: 0 };

// Internal component to house the React Flow logic
const FlowRenderer: React.FC<FlowChartPanelProps> = ({ processedSteps, isRightPanelVisible = false, isSidePanelTransitioning = false }) => {
    const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
    const { fitView } = useReactFlow();
    const { highlightedStepId, setHighlightedStepId } = useTaskContext();
    const { taskIdInSidePanel, agentNameDisplayNameMap } = useChatContext();

    const prevProcessedStepsRef = useRef<VisualizerStep[]>([]);
    const [hasUserInteracted, setHasUserInteracted] = useState(false);

    // Popover state for edge clicks
    const [selectedStep, setSelectedStep] = useState<VisualizerStep | null>(null);
    const [isPopoverOpen, setIsPopoverOpen] = useState(false);
    const popoverAnchorRef = useRef<HTMLDivElement>(null);

    // Track selected edge for highlighting
    const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);

    const edgeAnimationServiceRef = useRef<EdgeAnimationService>(new EdgeAnimationService());

    const memoizedFlowData = useMemo(() => {
        if (!processedSteps || processedSteps.length === 0) {
            return { nodes: [], edges: [] };
        }
        return transformProcessedStepsToTimelineFlow(processedSteps, agentNameDisplayNameMap);
    }, [processedSteps, agentNameDisplayNameMap]);

    // Consolidated edge computation
    const computedEdges = useMemo(() => {
        if (!memoizedFlowData.edges.length) return [];

        return memoizedFlowData.edges.map(edge => {
            const edgeData = edge.data as unknown as AnimatedEdgeData;

            // Determine animation state
            let animationState = { isAnimated: false, animationType: "none" };
            if (edgeData?.visualizerStepId) {
                const stepIndex = processedSteps.length - 1;
                animationState = edgeAnimationServiceRef.current.getEdgeAnimationState(edgeData.visualizerStepId, stepIndex, processedSteps);
            }

            // Determine if this edge should be selected
            let isSelected = edge.id === selectedEdgeId;

            // If highlightedStepId is set, also select the corresponding edge
            if (highlightedStepId && edgeData?.visualizerStepId === highlightedStepId) {
                isSelected = true;
            }

            return {
                ...edge,
                animated: animationState.isAnimated,
                data: {
                    ...edgeData,
                    isAnimated: animationState.isAnimated,
                    animationType: animationState.animationType,
                    isSelected,
                } as unknown as Record<string, unknown>,
            };
        });
    }, [memoizedFlowData.edges, processedSteps, selectedEdgeId, highlightedStepId]);

    const updateGroupNodeSizes = useCallback(() => {
        setNodes(currentNodes => {
            return currentNodes.map(node => {
                if (node.type !== "group") return node;

                // Find all child nodes of this group
                const childNodes = currentNodes.filter(n => n.parentId === node.id);
                if (childNodes.length === 0) return node;

                // Calculate required width and height based on child positions
                let maxX = 0;
                let maxY = 0;

                childNodes.forEach(child => {
                    const childRight = child.position.x + NODE_WIDTH;
                    const childBottom = child.position.y + NODE_HEIGHT;
                    maxX = Math.max(maxX, childRight);
                    maxY = Math.max(maxY, childBottom);
                });

                // Add padding
                const requiredWidth = maxX + GROUP_PADDING_X;
                const requiredHeight = maxY + GROUP_PADDING_Y;

                // Ensure minimum width for indented groups
                // Extract indentation level from group ID if possible
                let indentationLevel = 0;
                const groupIdParts = node.id.split("_");
                if (groupIdParts.length > 2) {
                    // Try to extract the subflow number which correlates with indentation level
                    const subflowPart = groupIdParts.find(part => part.startsWith("subflow"));
                    if (subflowPart) {
                        const subflowNum = parseInt(subflowPart.replace("subflow", ""));
                        if (!isNaN(subflowNum)) {
                            indentationLevel = subflowNum;
                        }
                    }
                }

                // Add extra space for indented tool nodes
                const minRequiredWidth = NODE_WIDTH + 2 * GROUP_PADDING_X + indentationLevel * 50;
                const finalRequiredWidth = Math.max(requiredWidth, minRequiredWidth);

                // Update group node style if needed
                const currentWidth = parseInt(node.style?.width?.toString().replace("px", "") || "0");
                const currentHeight = parseInt(node.style?.height?.toString().replace("px", "") || "0");

                if (currentWidth !== finalRequiredWidth || currentHeight !== requiredHeight) {
                    return {
                        ...node,
                        style: {
                            ...node.style,
                            width: `${finalRequiredWidth}px`,
                            height: `${requiredHeight}px`,
                        },
                    };
                }

                return node;
            });
        });
    }, [setNodes]);

    useEffect(() => {
        setNodes(memoizedFlowData.nodes);
        setEdges(computedEdges);
        updateGroupNodeSizes();
    }, [memoizedFlowData.nodes, computedEdges, setNodes, setEdges, updateGroupNodeSizes]);

    const findEdgeBySourceAndHandle = useCallback(
        (sourceNodeId: string, sourceHandleId?: string): Edge | null => {
            return edges.find(edge => edge.source === sourceNodeId && (sourceHandleId ? edge.sourceHandle === sourceHandleId : true)) || null;
        },
        [edges]
    );

    const handleEdgeClick = useCallback(
        (_event: React.MouseEvent, edge: Edge) => {
            setHasUserInteracted(true);

            const stepId = edge.data?.visualizerStepId as string;
            if (stepId) {
                const step = processedSteps.find(s => s.id === stepId);
                if (step) {
                    setSelectedEdgeId(edge.id);

                    if (isRightPanelVisible) {
                        setHighlightedStepId(stepId);
                    } else {
                        setHighlightedStepId(stepId);
                        setSelectedStep(step);
                        setIsPopoverOpen(true);
                    }
                }
            }
        },
        [processedSteps, isRightPanelVisible, setHighlightedStepId]
    );

    const getNodeSourceHandles = useCallback((node: Node): string[] => {
        switch (node.type) {
            case "userNode": {
                const userData = node.data as { isTopNode?: boolean; isBottomNode?: boolean };
                if (userData?.isTopNode) return ["user-bottom-output"];
                if (userData?.isBottomNode) return ["user-top-input"];
                return ["user-right-output"];
            }
            case "orchestratorNode":
                return ["orch-right-output-tools", "orch-bottom-output"];

            case "genericAgentNode":
                return ["peer-right-output-tools", "peer-bottom-output"];

            case "llmNode":
                return ["llm-bottom-output"];

            case "genericToolNode":
                return [`${node.id}-tool-bottom-output`];

            default:
                return [];
        }
    }, []);

    const handlePopoverClose = useCallback(() => {
        setIsPopoverOpen(false);
        setSelectedStep(null);
    }, []);

    const handleNodeClick = useCallback(
        (_event: React.MouseEvent, node: Node) => {
            setHasUserInteracted(true);

            // If clicking on a group container, treat it like clicking on empty space
            if (node.type === "group") {
                setHighlightedStepId(null);
                setSelectedEdgeId(null);
                handlePopoverClose();
                return;
            }

            const sourceHandles = getNodeSourceHandles(node);

            let targetEdge: Edge | null = null;
            for (const handleId of sourceHandles) {
                targetEdge = findEdgeBySourceAndHandle(node.id, handleId);

                if (targetEdge) break;
            }

            // Special case for bottom UserNode - check for incoming edges instead
            if (!targetEdge && node.type === "userNode") {
                const userData = node.data as { isBottomNode?: boolean };
                if (userData?.isBottomNode) {
                    targetEdge = edges.find(edge => edge.target === node.id) || null;
                }
            }

            if (targetEdge) {
                handleEdgeClick(_event, targetEdge);
            }
        },
        [getNodeSourceHandles, setHighlightedStepId, handlePopoverClose, findEdgeBySourceAndHandle, edges, handleEdgeClick]
    );

    const handleUserMove = useCallback((event: MouseEvent | TouchEvent | null) => {
        if (!event?.isTrusted) return; // Ignore synthetic events
        setHasUserInteracted(true);
    }, []);

    // Reset user interaction state when taskIdInSidePanel changes (new task loaded)
    useEffect(() => {
        setHasUserInteracted(false);
    }, [taskIdInSidePanel]);

    useEffect(() => {
        // Only run fitView if the panel is NOT transitioning AND user hasn't interacted
        if (!isSidePanelTransitioning && fitView && nodes.length > 0) {
            const shouldFitView = prevProcessedStepsRef.current !== processedSteps && hasUserInteracted === false;
            if (shouldFitView) {
                fitView({
                    duration: 200,
                    padding: 0.1,
                    maxZoom: 1.2,
                });

                prevProcessedStepsRef.current = processedSteps;
            }
        }
    }, [nodes.length, fitView, processedSteps, isSidePanelTransitioning, hasUserInteracted]);

    // Combined effect for node highlighting and edge selection based on highlightedStepId
    useEffect(() => {
        // Update node highlighting
        setNodes(currentFlowNodes =>
            currentFlowNodes.map(flowNode => {
                const isHighlighted = flowNode.data?.visualizerStepId && flowNode.data.visualizerStepId === highlightedStepId;

                // Find the original node from memoizedFlowData to get its base style
                const originalNode = memoizedFlowData.nodes.find(n => n.id === flowNode.id);
                const baseStyle = originalNode?.style || {};

                return {
                    ...flowNode,
                    style: {
                        ...baseStyle,
                        boxShadow: isHighlighted ? "0px 4px 12px rgba(0, 0, 0, 0.2)" : baseStyle.boxShadow || "none",
                        transition: "box-shadow 0.2s ease-in-out",
                    },
                };
            })
        );

        // Update selected edge
        if (highlightedStepId) {
            const relatedEdge = computedEdges.find(edge => {
                const edgeData = edge.data as unknown as AnimatedEdgeData;
                return edgeData?.visualizerStepId === highlightedStepId;
            });

            if (relatedEdge) {
                setSelectedEdgeId(relatedEdge.id);
            }
        } else {
            setSelectedEdgeId(null);
        }
    }, [highlightedStepId, setNodes, memoizedFlowData.nodes, computedEdges]);

    if (!processedSteps || processedSteps.length === 0) {
        return <div className="flex h-full items-center justify-center text-gray-500 dark:text-gray-400">{Object.keys(processedSteps).length > 0 ? "Processing flow data..." : "No steps to display in flow chart."}</div>;
    }

    if (memoizedFlowData.nodes.length === 0 && processedSteps.length > 0) {
        return <div className="flex h-full items-center justify-center text-gray-500 dark:text-gray-400">Generating flow chart...</div>;
    }

    return (
        <div style={{ height: "100%", width: "100%" }} className="relative">
            <ReactFlow
                nodes={nodes}
                edges={edges.map(edge => ({
                    ...edge,
                    markerEnd: { type: MarkerType.ArrowClosed, color: "#888" },
                }))}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onEdgeClick={handleEdgeClick}
                onNodeClick={handleNodeClick}
                onPaneClick={() => {
                    setHighlightedStepId(null);
                    setSelectedEdgeId(null);
                    handlePopoverClose();
                }}
                onMoveStart={handleUserMove}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                fitViewOptions={{ padding: 0.1 }}
                className={"bg-gray-50 dark:bg-gray-900 [&>button]:dark:bg-gray-700"}
                proOptions={{ hideAttribution: true }}
                nodesDraggable={false}
                elementsSelectable={false}
                nodesConnectable={false}
                minZoom={0.2}
            >
                <Background />
                <Controls className={getThemeButtonHtmlStyles()} />
                <Panel position="top-right" className="flex items-center space-x-4">
                    <div ref={popoverAnchorRef} />
                </Panel>
            </ReactFlow>

            {/* Edge Information Popover */}
            <PopoverManual isOpen={isPopoverOpen} onClose={handlePopoverClose} anchorRef={popoverAnchorRef} offset={POPOVER_OFFSET} placement="right-start" className="max-w-[500px] min-w-[400px] p-2">
                {selectedStep && <VisualizerStepCard step={selectedStep} variant="popover" />}
            </PopoverManual>
        </div>
    );
};

const FlowChartPanel: React.FC<FlowChartPanelProps> = props => {
    return (
        <ReactFlowProvider>
            <FlowRenderer {...props} />
        </ReactFlowProvider>
    );
};

export { FlowChartPanel };
