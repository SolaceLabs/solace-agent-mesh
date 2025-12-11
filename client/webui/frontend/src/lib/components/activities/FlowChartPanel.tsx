import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Background, Controls, MarkerType, Panel, ReactFlow, ReactFlowProvider, useEdgesState, useNodesState, useReactFlow } from "@xyflow/react";
import type { Edge, Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { PopoverManual } from "@/lib/components/ui";
import { useTaskContext } from "@/lib/hooks";
import { useChatContext } from "@/lib/hooks";
import { useAgentCards } from "@/lib/hooks";
import type { VisualizerStep } from "@/lib/types";
import { getThemeButtonHtmlStyles } from "@/lib/utils";

import { EdgeAnimationService } from "./FlowChart/edgeAnimationService";
import { BlockBuilder } from "./FlowChart/layout/BlockBuilder";
import { adjustAgentSlots } from "./FlowChart/layout/LayoutBlock";
import GenericFlowEdge, { type AnimatedEdgeData } from "./FlowChart/customEdges/GenericFlowEdge";
import ConditionalNode from "./FlowChart/customNodes/ConditionalNode";
import GenericAgentNode from "./FlowChart/customNodes/GenericAgentNode";
import GenericToolNode from "./FlowChart/customNodes/GenericToolNode";
import GroupNode from "./FlowChart/customNodes/GroupNode";
import LLMNode from "./FlowChart/customNodes/LLMNode";
import OrchestratorAgentNode from "./FlowChart/customNodes/OrchestratorAgentNode";
import UserNode from "./FlowChart/customNodes/UserNode";
import { VisualizerStepCard } from "./VisualizerStepCard";
import { FlowChartPanelV2 } from "./FlowChart/v2";
import { FlowChartPanelV3 } from "./FlowChart/v3";
import { FlowChartPanelV4 } from "./FlowChart/v4";

interface FlowChartPanelProps {
    processedSteps: VisualizerStep[];
    isRightPanelVisible?: boolean;
    isSidePanelTransitioning?: boolean;
}

// Stable offset object to prevent unnecessary re-renders
const POPOVER_OFFSET = { x: 16, y: 0 };

// Internal component to house the React Flow logic
const FlowRenderer: React.FC<FlowChartPanelProps> = ({ processedSteps, isRightPanelVisible = false, isSidePanelTransitioning = false }) => {
    const nodeTypes = useMemo(
        () => ({
            genericAgentNode: GenericAgentNode,
            userNode: UserNode,
            llmNode: LLMNode,
            orchestratorNode: OrchestratorAgentNode,
            genericToolNode: GenericToolNode,
            conditionalNode: ConditionalNode,
            group: GroupNode,
        }),
        []
    );

    const edgeTypes = useMemo(
        () => ({
            defaultFlowEdge: GenericFlowEdge,
        }),
        []
    );

    const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
    const { fitView } = useReactFlow();
    const { highlightedStepId, setHighlightedStepId } = useTaskContext();
    const { taskIdInSidePanel } = useChatContext();
    const { agentNameMap } = useAgentCards();

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

        try {
            const builder = new BlockBuilder(agentNameMap);
            const { root, edges } = builder.build(processedSteps);
            root.measure();
            root.layout();
            root.resolveAbsolutePositions(300, 0); // Start with offset to accommodate User lane on left
            
            builder.printTree();

            const nodes = root.collectNodes();
            adjustAgentSlots(nodes);
            return { nodes, edges };
        } catch (e) {
            console.error("BlockBuilder Error:", e);
            return { nodes: [], edges: [] };
        }
    }, [processedSteps, agentNameMap]);

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

    useEffect(() => {
        setNodes(memoizedFlowData.nodes);
        setEdges(computedEdges);

        // Debug logging for node positions
        if (memoizedFlowData.nodes.length > 0) {
            console.groupCollapsed("FlowChart Node Layout Summary");
            console.table(memoizedFlowData.nodes.map(n => ({
                id: n.id,
                type: n.type,
                label: n.data.label,
                x: n.position.x,
                y: n.position.y,
                width: n.style?.width,
                height: n.style?.height,
                parentId: n.parentId
            })));
            console.groupEnd();
        }
    }, [memoizedFlowData.nodes, computedEdges, setNodes, setEdges]);

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

            const startStepId = node.data?.visualizerStepId as string;
            if (!startStepId) return;

            const startStep = processedSteps.find(s => s.id === startStepId);
            if (!startStep) return;

            setHighlightedStepId(startStepId);
            setSelectedStep(startStep);
            setIsPopoverOpen(true);
            setSelectedEdgeId(null);
        },
        [processedSteps, setHighlightedStepId, handlePopoverClose]
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
    // Layout versions:
    // 'v1' = React Flow (original)
    // 'v2' = Contained layout (tools inside agents)
    // 'v3' = Subway/git-style graph
    // 'v4' = Hybrid: contained agents + subway tracks (default)
    const [layoutVersion, setLayoutVersion] = useState<'v1' | 'v2' | 'v3' | 'v4'>(() => {
        // Load from localStorage or default to v4
        const stored = localStorage.getItem('flowChartLayoutVersion');
        return (stored as 'v1' | 'v2' | 'v3' | 'v4') || 'v4';
    });

    const handleVersionChange = useCallback((version: 'v1' | 'v2' | 'v3' | 'v4') => {
        setLayoutVersion(version);
        localStorage.setItem('flowChartLayoutVersion', version);
    }, []);

    // Render version selector overlay
    const renderVersionSelector = () => (
        <div className="absolute top-4 left-4 z-50 flex items-center gap-3 bg-white dark:bg-gray-800 px-4 py-2 rounded-md shadow-md border border-gray-200 dark:border-gray-700">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Layout
            </span>
            <select
                value={layoutVersion}
                onChange={(e) => handleVersionChange(e.target.value as 'v1' | 'v2' | 'v3' | 'v4')}
                className="text-sm font-medium bg-transparent border-none outline-none cursor-pointer text-gray-900 dark:text-gray-100"
                title="Select Layout Version"
            >
                <option value="v4">V4: Hybrid</option>
                <option value="v3">V3: Subway</option>
                <option value="v2">V2: Contained</option>
                <option value="v1">V1: React Flow</option>
            </select>
        </div>
    );

    if (layoutVersion === 'v4') {
        return (
            <div className="relative w-full h-full">
                {renderVersionSelector()}
                <FlowChartPanelV4 {...props} />
            </div>
        );
    }

    if (layoutVersion === 'v3') {
        return (
            <div className="relative w-full h-full">
                {renderVersionSelector()}
                <FlowChartPanelV3 {...props} />
            </div>
        );
    }

    if (layoutVersion === 'v2') {
        return (
            <div className="relative w-full h-full">
                {renderVersionSelector()}
                <FlowChartPanelV2 {...props} />
            </div>
        );
    }

    return (
        <div className="relative w-full h-full">
            {renderVersionSelector()}
            <ReactFlowProvider>
                <FlowRenderer {...props} />
            </ReactFlowProvider>
        </div>
    );
};

export { FlowChartPanel };
