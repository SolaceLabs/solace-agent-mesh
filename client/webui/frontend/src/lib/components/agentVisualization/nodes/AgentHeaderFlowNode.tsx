import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import type { AgentFlowNodeData } from "../utils/types";
import AgentHeaderNode from "./AgentHeaderNode";

const HANDLE_STYLE = { width: 1, height: 1, background: "transparent", border: "none", minWidth: 0, minHeight: 0 };

export default function AgentHeaderFlowNode({ data }: NodeProps<Node<AgentFlowNodeData>>) {
    return (
        <>
            <AgentHeaderNode node={data.agentLayoutNode} />
            <Handle type="source" position={Position.Right} id="right" style={HANDLE_STYLE} />
            <Handle type="source" position={Position.Bottom} id="bottom" style={HANDLE_STYLE} />
        </>
    );
}
