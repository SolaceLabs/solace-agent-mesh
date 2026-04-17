import React from "react";
import type { AgentLayoutNode } from "./utils/types";
import AgentHeaderNode from "./nodes/AgentHeaderNode";
import ToolNode from "./nodes/ToolNode";
import SkillNode from "./nodes/SkillNode";
import ToolsetGroupNode from "./nodes/ToolsetGroupNode";

interface AgentNodeRendererProps {
    nodes: AgentLayoutNode[];
    selectedNodeId?: string;
    onNodeClick?: (node: AgentLayoutNode) => void;
}

/**
 * AgentNodeRenderer - Renders positioned agent diagram nodes at their absolute positions
 */
const AgentNodeRenderer: React.FC<AgentNodeRendererProps> = ({ nodes, selectedNodeId, onNodeClick }) => {
    const renderNode = (node: AgentLayoutNode) => {
        const isSelected = node.id === selectedNodeId;
        const commonProps = { node, isSelected, onClick: onNodeClick };

        switch (node.type) {
            case "agent-header":
                return <AgentHeaderNode {...commonProps} />;
            case "tool":
                return <ToolNode {...commonProps} />;
            case "skill":
                return <SkillNode {...commonProps} />;
            case "toolset-group":
                return <ToolsetGroupNode {...commonProps} />;
            default:
                return null;
        }
    };

    return (
        <>
            {nodes.map(node => (
                <div
                    key={node.id}
                    style={{
                        position: "absolute",
                        left: `${node.x}px`,
                        top: `${node.y}px`,
                    }}
                >
                    {renderNode(node)}
                </div>
            ))}
        </>
    );
};

export default AgentNodeRenderer;
