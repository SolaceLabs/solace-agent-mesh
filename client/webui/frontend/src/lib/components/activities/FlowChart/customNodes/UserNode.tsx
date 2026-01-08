import React from "react";
import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import type { GenericNodeData } from "./GenericAgentNode";

export interface UserNodeData extends GenericNodeData {
    isTopNode?: boolean; // true if created by handleUserRequest
    isBottomNode?: boolean; // true if created by createNewUserNodeAtBottom
}

export type UserNodeType = Node<UserNodeData>;

const UserNode: React.FC<NodeProps<UserNodeType>> = ({ data }) => {
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
                return "bg-purple-500";
        }
    };

    return (
        <div
            className="cursor-pointer rounded-md border-2 border-purple-600 bg-white px-4 py-3 text-gray-800 shadow-lg transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-xl dark:border-purple-400 dark:bg-gray-700 dark:text-gray-200"
            style={{ minWidth: "120px", textAlign: "center" }}
        >
            {data.isTopNode && <Handle type="source" position={Position.Bottom} id="user-bottom-output" className="!bg-gray-500" isConnectable={true} />}
            {data.isBottomNode && <Handle type="target" position={Position.Top} id="user-top-input" className="!bg-gray-500" isConnectable={true} />}
            {!data.isTopNode && !data.isBottomNode && <Handle type="source" position={Position.Right} id="user-right-output" className="!bg-gray-500" isConnectable={true} />}
            <div className="flex items-center justify-center">
                <div className={`mr-2 h-3 w-3 rounded-full ${getStatusColor()}`} />
                <div className="text-sm font-bold">{data.label}</div>
            </div>
        </div>
    );
};

export default UserNode;
