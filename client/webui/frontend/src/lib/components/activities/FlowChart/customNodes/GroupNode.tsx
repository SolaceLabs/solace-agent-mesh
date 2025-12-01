import React from "react";
import { type NodeProps, type Node } from "@xyflow/react";

export type GroupNodeType = Node<{ label: string }>;

const GroupNode: React.FC<NodeProps<GroupNodeType>> = ({ data }) => {
    return (
        <div className="h-full w-full pointer-events-none relative">
            {data.label && (
                <div className="absolute -top-3 left-4 px-2 text-xs font-bold text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-900 rounded-md border border-gray-200 dark:border-gray-700">
                    {data.label}
                </div>
            )}
        </div>
    );
};

export default GroupNode;
