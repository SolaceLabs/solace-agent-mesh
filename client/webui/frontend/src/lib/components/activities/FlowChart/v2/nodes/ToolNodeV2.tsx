import React from "react";
import type { LayoutNode } from "../utils/types";

interface ToolNodeV2Props {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
}

const ToolNodeV2: React.FC<ToolNodeV2Props> = ({ node, isSelected, onClick }) => {
    const getStatusColor = () => {
        switch (node.data.status) {
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
            className={`cursor-pointer rounded-lg border-2 border-cyan-600 bg-white px-3 py-2 text-gray-800 shadow-md transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-xl dark:border-cyan-400 dark:bg-gray-800 dark:text-gray-200 ${
                isSelected ? "ring-2 ring-blue-500" : ""
            }`}
            style={{
                width: `${node.width}px`,
                minWidth: "100px",
                textAlign: "center",
            }}
            onClick={() => onClick?.(node)}
            title={node.data.description}
        >
            <div className="flex items-center justify-center">
                <div className={`mr-2 h-2 w-2 rounded-full ${getStatusColor()}`} />
                <div className="text-sm truncate" style={{ maxWidth: "150px" }}>
                    {node.data.label}
                </div>
            </div>
        </div>
    );
};

export default ToolNodeV2;
