import React from "react";
import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import type { GenericNodeData } from "./GenericAgentNode";

export interface ConditionalNodeData extends GenericNodeData {
    condition?: string;
    trueBranch?: string;
    falseBranch?: string;
    trueBranchLabel?: string;
    falseBranchLabel?: string;
}

export type ConditionalNodeType = Node<ConditionalNodeData>;

const ConditionalNode: React.FC<NodeProps<ConditionalNodeType>> = ({ data }) => {
    const getStatusColor = () => {
        switch (data.status) {
            case "completed":
                return "bg-amber-100 border-amber-500 dark:bg-amber-900/30 dark:border-amber-500";
            case "in-progress":
                return "bg-blue-100 border-blue-500 dark:bg-blue-900/30 dark:border-blue-500";
            case "error":
                return "bg-red-100 border-red-500 dark:bg-red-900/30 dark:border-red-500";
            default:
                return "bg-gray-100 border-gray-400 dark:bg-gray-800 dark:border-gray-600";
        }
    };

    return (
        <div className="relative flex items-center justify-center" style={{ width: "120px", height: "80px" }}>
            {/* Diamond Shape using rotation */}
            <div
                className={`absolute h-12 w-12 rotate-45 border-2 shadow-sm transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-md ${getStatusColor()}`}
            />

            {/* Content (unrotated) */}
            <div className="z-10 flex flex-col items-center justify-center text-center pointer-events-none px-1">
                <div className="text-[10px] font-bold text-gray-800 dark:text-gray-200 max-w-[100px] truncate" title={data.label}>
                    {data.label}
                </div>
            </div>

            {/* Handles - positioned relative to the unrotated container */}
            <Handle type="target" position={Position.Top} id="cond-top-input" className="!bg-gray-500" isConnectable={true} />
            <Handle type="source" position={Position.Bottom} id="cond-bottom-output" className="!bg-gray-500" isConnectable={true} />
            <Handle type="source" position={Position.Right} id="cond-right-output" className="!bg-gray-500" isConnectable={true} />
        </div>
    );
};

export default ConditionalNode;
