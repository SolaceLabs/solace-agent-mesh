import React from "react";
import type { LayoutNode } from "../utils/types";

interface UserNodeV2Props {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
}

const UserNodeV2: React.FC<UserNodeV2Props> = ({ node, isSelected, onClick }) => {
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
                return "bg-purple-500";
        }
    };

    return (
        <div
            className={`cursor-pointer rounded-md border-2 border-purple-600 bg-white px-4 py-3 text-gray-800 shadow-lg transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-xl dark:border-purple-400 dark:bg-gray-700 dark:text-gray-200 ${
                isSelected ? "ring-2 ring-blue-500" : ""
            }`}
            style={{
                minWidth: "120px",
                textAlign: "center",
            }}
            onClick={(e) => {
                e.stopPropagation();
                onClick?.(node);
            }}
        >
            <div className="flex items-center justify-center">
                <div className={`mr-2 h-3 w-3 rounded-full ${getStatusColor()}`} />
                <div className="text-sm font-bold">{node.data.label}</div>
            </div>
        </div>
    );
};

export default UserNodeV2;
