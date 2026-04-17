import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import type { WorkflowFlowNodeData } from "../utils/types";
import StartNode from "./StartNode";

const HANDLE_STYLE = { width: 1, height: 1, background: "transparent", border: "none", minWidth: 0, minHeight: 0 };

export default function StartFlowNode({ data }: NodeProps<Node<WorkflowFlowNodeData>>) {
    const isHighlighted = data.highlightedNodeIds?.has(data.layoutNode.id) ?? false;
    return (
        <>
            <StartNode node={data.layoutNode} isHighlighted={isHighlighted} />
            <Handle type="source" position={Position.Bottom} id="bottom" style={HANDLE_STYLE} />
        </>
    );
}
