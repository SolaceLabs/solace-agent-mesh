import React from "react";

import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";

import type { GenericNodeData } from "./GenericAgentNode";

export type LLMNodeType = Node<GenericNodeData>;

const LLMNode: React.FC<NodeProps<LLMNodeType>> = ({ data }) => {
    const getStatusColor = () => {
        switch (data.status) {
            case "completed":
                return "bg-green-500";
            case "in-progress":
                return "bg-blue-500";
            case "error":
                return "bg-red-500";
            case "started":
                return "bg-yellow-400";
            case "idle":
            default:
                return "bg-teal-500";
        }
    };

    return (
        <div
            className="cursor-pointer rounded-lg border-2 border-teal-600 bg-white px-3 py-3 text-gray-800 shadow-md transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-xl dark:border-teal-400 dark:bg-gray-800 dark:text-gray-200"
            style={{ minWidth: "100px", textAlign: "center" }}
        >
            <Handle type="target" position={Position.Left} id="llm-left-input" className="!bg-teal-500" isConnectable={true} style={{ top: "25%" }} />
            <div className="flex items-center justify-center">
                <div className={`mr-2 h-2 w-2 rounded-full ${getStatusColor()}`} />
                <div className="text-md">{data.label}</div>
            </div>
            <Handle type="source" position={Position.Left} id="llm-bottom-output" className="!bg-teal-500" isConnectable={true} style={{ top: "75%" }} />
        </div>
    );
};

export default LLMNode;
