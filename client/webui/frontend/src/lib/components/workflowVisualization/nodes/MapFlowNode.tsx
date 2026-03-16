import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import type { LayoutNode, WorkflowFlowNodeData } from "../utils/types";
import MapNode from "./MapNode";
import { renderWorkflowChild } from "./renderWorkflowChild";

const HANDLE_STYLE = { width: 1, height: 1, background: "transparent", border: "none", minWidth: 0, minHeight: 0 };

export default function MapFlowNode({ data, selected }: NodeProps<Node<WorkflowFlowNodeData>>) {
    const isHighlighted = data.highlightedNodeIds?.has(data.layoutNode.id) ?? false;

    const renderChildren = (children: LayoutNode[]) =>
        children.map(child => (
            <div key={child.id} style={{ position: "relative" }}>
                {renderWorkflowChild(child, data)}
            </div>
        ));

    return (
        <>
            <Handle type="target" position={Position.Top} id="top" style={HANDLE_STYLE} />
            <MapNode
                node={data.layoutNode}
                isSelected={selected}
                isHighlighted={isHighlighted}
                onExpand={data.onExpand}
                onCollapse={data.onCollapse}
                renderChildren={renderChildren}
            />
            <Handle type="source" position={Position.Bottom} id="bottom" style={HANDLE_STYLE} />
        </>
    );
}
