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
            className={`cursor-pointer rounded-md border-2 border-(--color-accent-n3-wMain) bg-(--color-background-w10) px-4 py-3 text-(--color-primary-text-wMain) shadow-md transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-xl dark:border-(--color-accent-n3-w30) dark:bg-(--color-background-wMain) dark:text-(--color-primary-text-w10) ${
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
            <div className="flex items-center justify-center gap-2">
                <User className="h-4 w-4 flex-shrink-0 text-(--color-accent-n3-wMain) dark:text-(--color-accent-n3-w30)" />
                <div className="text-sm font-bold">{node.data.label}</div>
            </div>
        </div>
    );
};

export default UserNode;
