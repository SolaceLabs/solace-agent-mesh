import React from "react";

import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";

import type { GenericNodeData } from "./GenericAgentNode";

export type OrchestratorAgentNodeType = Node<GenericNodeData>;

const OrchestratorAgentNode: React.FC<NodeProps<OrchestratorAgentNodeType>> = ({ data }) => {
    return (
        <div
            className="cursor-pointer rounded-lg border-indigo-600 bg-gradient-to-r from-indigo-50 to-purple-50 px-5 py-3 text-gray-900 shadow-xl transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-2xl dark:border-indigo-400 dark:bg-gradient-to-r dark:from-indigo-900 dark:to-purple-900 dark:text-gray-100"
            style={{
                minWidth: "180px",
                textAlign: "center",
                borderWidth: "2px",
                borderStyle: "solid",
                boxShadow: "0 0 0 1px rgba(79, 70, 229, 0.3), 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
            }}
        >
            <Handle type="source" position={Position.Right} id="orch-right-output-tools" className="!bg-indigo-500" style={{ top: "25%" }} isConnectable={true} />
            <Handle type="target" position={Position.Right} id="orch-right-input-tools" className="!bg-indigo-500" style={{ top: "75%" }} isConnectable={true} />
            <Handle type="target" position={Position.Top} id="orch-top-input" className="!bg-indigo-500" isConnectable={true} />
            <Handle type="source" position={Position.Bottom} id="orch-bottom-output" className="!bg-indigo-500" isConnectable={true} />
            <Handle type="target" position={Position.Left} id="orch-left-input" className="!bg-indigo-500" isConnectable={true} />
            <div className="flex items-center justify-center">
                <div className="text-md truncate font-bold" style={{ maxWidth: "200px" }}>
                    {data.label}
                </div>
            </div>
        </div>
    );
};

export default OrchestratorAgentNode;
