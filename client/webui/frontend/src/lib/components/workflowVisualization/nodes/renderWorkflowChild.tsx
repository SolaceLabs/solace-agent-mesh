import type { ReactNode } from "react";
import type { LayoutNode, WorkflowFlowNodeData } from "../utils/types";
import StartNode from "./StartNode";
import EndNode from "./EndNode";
import AgentNode from "./AgentNode";
import WorkflowRefNode from "./WorkflowRefNode";
import SwitchNode from "./SwitchNode";
import ConditionPillNode from "./ConditionPillNode";
import MapNode from "./MapNode";
import LoopNode from "./LoopNode";

/**
 * Render a workflow node inside a container (Map/Loop).
 * Used by container flow node wrappers to render their children.
 */
export function renderWorkflowChild(child: LayoutNode, data: WorkflowFlowNodeData): ReactNode {
    const isSelected = child.id === data.selectedNodeId;
    const isHighlighted = data.highlightedNodeIds?.has(child.id) ?? false;

    const commonProps = {
        node: child,
        isSelected,
        isHighlighted,
        onClick: data.onNodeClick,
        onExpand: data.onExpand,
        onCollapse: data.onCollapse,
        onHighlightNodes: data.onHighlightNodes,
        knownNodeIds: data.knownNodeIds,
        currentWorkflowName: data.currentWorkflowName,
        parentPath: data.parentPath,
    };

    const makeRenderChildren = () => (children: LayoutNode[]) =>
        children.map(c => (
            <div key={c.id} style={{ position: "relative" }}>
                {renderWorkflowChild(c, data)}
            </div>
        ));

    switch (child.type) {
        case "start":
            return <StartNode {...commonProps} />;
        case "end":
            return <EndNode {...commonProps} />;
        case "agent":
            return <AgentNode {...commonProps} />;
        case "workflow":
            return <WorkflowRefNode {...commonProps} />;
        case "switch":
            return <SwitchNode {...commonProps} />;
        case "condition":
            return <ConditionPillNode {...commonProps} />;
        case "map":
            return <MapNode {...commonProps} renderChildren={makeRenderChildren()} />;
        case "loop":
            return <LoopNode {...commonProps} renderChildren={makeRenderChildren()} />;
        default:
            return null;
    }
}
