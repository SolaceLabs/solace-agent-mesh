import React from "react";

import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";

export interface GenericNodeData extends Record<string, unknown> {
    label: string;
    description?: string;
    icon?: string;
    subflow?: boolean;
    isInitial?: boolean;
    isFinal?: boolean;
}

const GenericAgentNode: React.FC<NodeProps<Node<GenericNodeData>>> = ({ data }) => {
    return (
        <div
            className="cursor-pointer rounded-md border-2 border-blue-700 bg-white px-5 py-3 text-gray-800 shadow-md transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-xl dark:border-blue-600 dark:bg-gray-800 dark:text-gray-200"
            style={{ minWidth: "180px", textAlign: "center" }}
        >
            <Handle type="target" position={Position.Top} id="peer-top-input" className="!bg-blue-700" isConnectable={true} />
            <Handle type="source" position={Position.Right} id="peer-right-output-tools" className="!bg-blue-700" style={{ top: "25%" }} isConnectable={true} />
            <Handle type="target" position={Position.Right} id="peer-right-input-tools" className="!bg-blue-700" style={{ top: "75%" }} isConnectable={true} />
            <Handle type="source" position={Position.Bottom} id="peer-bottom-output" className="!bg-blue-700" isConnectable={true} />
            <Handle type="target" position={Position.Left} id="peer-left-input" className="!bg-blue-700" isConnectable={true} />
            <div className="flex items-center justify-center">
                <div className="text-md truncate font-semibold" style={{ maxWidth: "200px" }}>
                    {data.label}
                </div>
            </div>
        </div>
    );
};

export default GenericAgentNode;
