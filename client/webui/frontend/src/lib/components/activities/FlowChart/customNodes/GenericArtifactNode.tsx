import React from "react";

import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";

import type { GenericNodeData } from "./GenericAgentNode";

export type ArtifactNodeType = Node<GenericNodeData>;

const ArtifactNode: React.FC<NodeProps<ArtifactNodeType>> = ({ data, id }) => {
    return (
        <div
            className="cursor-pointer rounded-lg border-2 border-purple-600 bg-white px-3 py-3 text-gray-800 shadow-md transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-xl dark:border-purple-400 dark:bg-gray-800 dark:text-gray-200"
            style={{ minWidth: "120px", textAlign: "center" }}
        >
            <Handle type="target" position={Position.Left} id={`${id}-artifact-left-input`} className="!bg-purple-500" isConnectable={true} />
            <div className="flex flex-col items-center justify-center gap-1">
                <div className="flex items-center justify-center">
                    <div className="mr-2 h-2 w-2 rounded-full bg-purple-500" />
                    <div className="text-md">{data.label}</div>
                </div>
            </div>
        </div>
    );
};

export default ArtifactNode;
