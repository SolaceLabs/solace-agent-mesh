import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import type { WorkflowFlowNodeData } from "../utils/types";
import WorkflowRefNode from "./WorkflowRefNode";

const HANDLE_STYLE = { width: 1, height: 1, background: "transparent", border: "none", minWidth: 0, minHeight: 0 };

export default function WorkflowRefFlowNode({ data, selected }: NodeProps<Node<WorkflowFlowNodeData>>) {
    const isHighlighted = data.highlightedNodeIds?.has(data.layoutNode.id) ?? false;
    return (
        <>
            <Handle type="target" position={Position.Top} id="top" style={HANDLE_STYLE} />
            <WorkflowRefNode node={data.layoutNode} isSelected={selected} isHighlighted={isHighlighted} />
            <Handle type="source" position={Position.Bottom} id="bottom" style={HANDLE_STYLE} />
        </>
    );
}
