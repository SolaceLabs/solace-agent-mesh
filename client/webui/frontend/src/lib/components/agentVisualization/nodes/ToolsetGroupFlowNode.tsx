import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import type { AgentFlowNodeData } from "../utils/types";
import ToolsetGroupNode from "./ToolsetGroupNode";

const HANDLE_STYLE = { width: 1, height: 1, background: "transparent", border: "none", minWidth: 0, minHeight: 0 };

export default function ToolsetGroupFlowNode({ data }: NodeProps<Node<AgentFlowNodeData>>) {
    return (
        <>
            <Handle type="target" position={Position.Left} id="left" style={HANDLE_STYLE} />
            <ToolsetGroupNode node={data.agentLayoutNode} />
        </>
    );
}
