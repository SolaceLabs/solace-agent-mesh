import React, { useMemo, useState } from "react";
import type { VisualizerStep } from "@/lib/types";
import { processSteps } from "./utils/layoutEngine";
import type { LayoutNode, Edge } from "./utils/types";
import AgentNodeV2 from "./nodes/AgentNodeV2";
import UserNodeV2 from "./nodes/UserNodeV2";
import WorkflowGroupV2 from "./nodes/WorkflowGroupV2";
import EdgeLayerV2 from "./EdgeLayerV2";

interface WorkflowRendererV2Props {
    processedSteps: VisualizerStep[];
    agentNameMap: Record<string, string>;
    selectedStepId?: string | null;
    onNodeClick?: (node: LayoutNode) => void;
    onEdgeClick?: (edge: Edge) => void;
}

const WorkflowRendererV2: React.FC<WorkflowRendererV2Props> = ({
    processedSteps,
    agentNameMap,
    selectedStepId,
    onNodeClick,
    onEdgeClick,
}) => {
    const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);

    // Process steps into layout
    const layoutResult = useMemo(() => {
        if (!processedSteps || processedSteps.length === 0) {
            return { nodes: [], edges: [], totalWidth: 800, totalHeight: 600 };
        }

        try {
            return processSteps(processedSteps, agentNameMap);
        } catch (error) {
            console.error("[WorkflowRendererV2] Error processing steps:", error);
            return { nodes: [], edges: [], totalWidth: 800, totalHeight: 600 };
        }
    }, [processedSteps, agentNameMap]);

    const { nodes, edges, totalWidth, totalHeight } = layoutResult;

    // Handle node click
    const handleNodeClick = (node: LayoutNode) => {
        onNodeClick?.(node);
    };

    // Handle edge click
    const handleEdgeClick = (edge: Edge) => {
        setSelectedEdgeId(edge.id);
        onEdgeClick?.(edge);
    };

    // Render a top-level node
    const renderNode = (node: LayoutNode) => {
        const isSelected = node.data.visualizerStepId === selectedStepId;

        const nodeProps = {
            node,
            isSelected,
            onClick: handleNodeClick,
            onChildClick: handleNodeClick, // For nested clicks
        };

        const style: React.CSSProperties = {
            position: "absolute",
            left: `${node.x}px`,
            top: `${node.y}px`,
            zIndex: 1,
        };

        let component: React.ReactNode;

        switch (node.type) {
            case 'agent':
                component = <AgentNodeV2 {...nodeProps} />;
                break;
            case 'user':
                component = <UserNodeV2 {...nodeProps} />;
                break;
            case 'group':
                component = <WorkflowGroupV2 {...nodeProps} />;
                break;
            default:
                return null;
        }

        return (
            <div key={node.id} style={style}>
                {component}
            </div>
        );
    };

    if (nodes.length === 0) {
        return (
            <div className="flex h-full items-center justify-center text-gray-500 dark:text-gray-400">
                {processedSteps.length > 0 ? "Processing flow data..." : "No steps to display in flow chart."}
            </div>
        );
    }

    return (
        <div
            style={{
                position: "relative",
                width: `${totalWidth}px`,
                height: `${totalHeight}px`,
                minWidth: "100%",
                minHeight: "100%",
            }}
        >
            {/* Edge Layer (SVG) */}
            <EdgeLayerV2
                edges={edges}
                selectedEdgeId={selectedEdgeId}
                onEdgeClick={handleEdgeClick}
            />

            {/* Nodes */}
            {nodes.map(renderNode)}
        </div>
    );
};

export default WorkflowRendererV2;
