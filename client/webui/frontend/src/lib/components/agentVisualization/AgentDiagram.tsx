import { useMemo, useState, useCallback, useEffect } from "react";
import { ReactFlow, ReactFlowProvider, MarkerType, useNodesState, type Node, type Edge, type NodeMouseHandler } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { processAgentConfig } from "./utils/layoutEngine";
import type { AgentDiagramConfig, AgentLayoutNode, AgentFlowNodeData } from "./utils/types";
import AgentHeaderFlowNode from "./nodes/AgentHeaderFlowNode";
import ToolFlowNode from "./nodes/ToolFlowNode";
import SkillFlowNode from "./nodes/SkillFlowNode";
import ToolsetGroupFlowNode from "./nodes/ToolsetGroupFlowNode";
import { AgentDiagramEdge } from "./AgentDiagramEdge";
import "./agentDiagram.css";

interface AgentDiagramProps {
    config: AgentDiagramConfig;
    onNodeSelect?: (node: AgentLayoutNode | null) => void;
    /** Additional CSS class for the root container (e.g. to override background) */
    className?: string;
}

const nodeTypes = {
    "agent-header": AgentHeaderFlowNode,
    "tool": ToolFlowNode,
    "skill": SkillFlowNode,
    "toolset-group": ToolsetGroupFlowNode,
};

const edgeTypes = {
    "agent-edge": AgentDiagramEdge,
};

const DEFAULT_EDGE_MARKER = {
    type: MarkerType.ArrowClosed,
    width: 16,
    height: 16,
};

/**
 * AgentDiagram - Main agent visualization component using ReactFlow.
 * Shows the agent at the top with tools to the right and skills below.
 */
const AgentDiagram: React.FC<AgentDiagramProps> = ({ config, onNodeSelect, className }) => {
    return (
        <div className={`agent-diagram ${className ?? "bg-card-background"} relative h-full w-full`}>
            <ReactFlowProvider>
                <AgentDiagramInner config={config} onNodeSelect={onNodeSelect} />
            </ReactFlowProvider>
        </div>
    );
};

const AgentDiagramInner: React.FC<Omit<AgentDiagramProps, "className">> = ({ config, onNodeSelect }) => {
    const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

    // Calculate layout whenever config changes
    const layout = useMemo(() => processAgentConfig(config), [config]);

    // Seed nodes from layout engine, then let ReactFlow manage positions (for dragging)
    const initialNodes = useMemo<Node<AgentFlowNodeData>[]>(() => {
        return layout.nodes.map(n => ({
            id: n.id,
            type: n.type,
            position: { x: n.x, y: n.y },
            data: { agentLayoutNode: n } as AgentFlowNodeData,
            width: n.width,
            height: n.height,
            selectable: true,
        }));
    }, [layout.nodes]);

    const [nodes, setNodes, onNodesChange] = useNodesState<Node<AgentFlowNodeData>>(initialNodes);

    // Re-sync when config changes (new tools/skills added)
    useEffect(() => {
        setNodes(initialNodes);
    }, [initialNodes, setNodes]);

    // Convert layout edges to ReactFlow edges
    const rfEdges = useMemo<Edge[]>(() => {
        return layout.edges.map(e => {
            const targetNode = layout.nodes.find(n => n.id === e.target);
            const isHorizontal = targetNode?.type === "tool" || targetNode?.type === "toolset-group";
            return {
                id: e.id,
                source: e.source,
                target: e.target,
                sourceHandle: isHorizontal ? "right" : "bottom",
                targetHandle: isHorizontal ? "left" : "top",
                type: "agent-edge",
                markerEnd: DEFAULT_EDGE_MARKER,
            };
        });
    }, [layout.edges, layout.nodes]);

    // Handle node click — map ReactFlow node back to AgentLayoutNode
    const handleNodeClick: NodeMouseHandler<Node<AgentFlowNodeData>> = useCallback(
        (_event, node) => {
            const agentNode = node.data.agentLayoutNode;
            setSelectedNodeId(agentNode.id);
            onNodeSelect?.(agentNode);
        },
        [onNodeSelect]
    );

    // Handle pane click — deselect
    const handlePaneClick = useCallback(() => {
        setSelectedNodeId(null);
        onNodeSelect?.(null);
    }, [onNodeSelect]);

    // Update selection state in node data when selectedNodeId changes
    const nodesWithSelection = useMemo<Node<AgentFlowNodeData>[]>(() => {
        return nodes.map(n => ({
            ...n,
            selected: n.id === selectedNodeId,
        }));
    }, [nodes, selectedNodeId]);

    return (
        <ReactFlow
            nodes={nodesWithSelection}
            edges={rfEdges}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            onNodesChange={onNodesChange}
            onNodeClick={handleNodeClick}
            onPaneClick={handlePaneClick}
            nodesDraggable={true}
            nodesConnectable={false}
            elementsSelectable={true}
            fitView
            fitViewOptions={{ padding: 0.15 }}
            minZoom={0.25}
            maxZoom={2}
            proOptions={{ hideAttribution: true }}
        />
    );
};

export default AgentDiagram;
