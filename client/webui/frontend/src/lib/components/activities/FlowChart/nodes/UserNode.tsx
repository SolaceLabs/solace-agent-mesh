import type { FC } from "react";
import { User } from "lucide-react";
import type { LayoutNode } from "../utils/types";

interface UserNodeProps {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
}

const UserNode: FC<UserNodeProps> = ({ node, isSelected, onClick }) => {
    return (
        <div
            className={`cursor-pointer rounded-md border-2 border-purple-600 bg-white px-4 py-3 text-gray-800 shadow-md transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-xl dark:border-purple-400 dark:bg-gray-800 dark:text-gray-200 ${
                isSelected ? "ring-2 ring-blue-500" : ""
            }`}
            style={{
                minWidth: "120px",
                textAlign: "center",
            }}
            onClick={e => {
                e.stopPropagation();
                onClick?.(node);
            }}
        >
            <div className="flex items-center justify-center gap-2" data-testid="userNode">
                <User className="h-4 w-4 flex-shrink-0 text-purple-600 dark:text-purple-400" />
                <div className="text-sm font-bold">{node.data.label}</div>
            </div>
        </div>
    );
};

export default UserNode;
