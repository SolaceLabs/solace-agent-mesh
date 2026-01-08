import React from "react";

import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";

import type { GenericNodeData } from "./GenericAgentNode";

export type GenericToolNodeType = Node<GenericNodeData>;

const GenericToolNode: React.FC<NodeProps<GenericToolNodeType>> = ({ data, id }) => {
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
                return "bg-cyan-500";
        }
    };

    return (
        <div
            className="cursor-pointer rounded-lg border-2 border-cyan-600 bg-white px-3 py-3 text-gray-800 shadow-md transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-xl dark:border-cyan-400 dark:bg-gray-800 dark:text-gray-200"
            style={{ minWidth: "100px", textAlign: "center" }}
        >
            <Handle type="target" position={Position.Left} id={`${id}-tool-left-input`} className="!bg-cyan-500" isConnectable={true} style={{ top: "25%" }} />
            <div className="flex items-center justify-center">
                <div className={`mr-2 h-2 w-2 rounded-full ${getStatusColor()}`} />
                <div className="text-md truncate" style={{ maxWidth: "200px" }}>
                    {data.label}
                </div>
            </div>
            <Handle type="source" position={Position.Left} id={`${id}-tool-bottom-output`} className="!bg-cyan-500" isConnectable={true} style={{ top: "75%" }} />
        </div>
    );
};

export default GenericToolNode;
