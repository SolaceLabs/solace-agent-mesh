import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import type { WorkflowFlowNodeData } from "../utils/types";
import ConditionPillNode from "./ConditionPillNode";

const HANDLE_STYLE = { width: 1, height: 1, background: "transparent", border: "none", minWidth: 0, minHeight: 0 };

export default function ConditionPillFlowNode({ data, selected }: NodeProps<Node<WorkflowFlowNodeData>>) {
    return (
        <>
            <Handle type="target" position={Position.Top} id="top" style={HANDLE_STYLE} />
            <ConditionPillNode
                node={data.layoutNode}
                isSelected={selected}
                onHighlightNodes={data.onHighlightNodes}
                knownNodeIds={data.knownNodeIds}
            />
            <Handle type="source" position={Position.Bottom} id="bottom" style={HANDLE_STYLE} />
        </>
    );
}
