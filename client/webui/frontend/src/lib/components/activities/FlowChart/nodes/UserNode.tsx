import type { FC } from "react";
import { User } from "lucide-react";

import type { LayoutNode } from "../utils/types";
import { ACTIVITY_NODE_BASE_STYLES, ACTIVITY_NODE_SELECTED_CLASS } from "../utils/nodeStyles";

interface UserNodeProps {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
}

const UserNode: FC<UserNodeProps> = ({ node, isSelected, onClick }) => {
    const USER_WIDTH = 100;

    return (
        <div
            className={`${ACTIVITY_NODE_BASE_STYLES.RECTANGULAR} ${isSelected ? ACTIVITY_NODE_SELECTED_CLASS : ""}`}
            style={{
                width: `${USER_WIDTH}px`,
            }}
            onClick={e => {
                e.stopPropagation();
                onClick?.(node);
            }}
        >
            <div className="flex items-center gap-2" data-testid="userNode">
                <User className="h-4 w-4 flex-shrink-0 text-(--color-brand-wMain)" />
                <div className="text-sm font-semibold">{node.data.label}</div>
            </div>
        </div>
    );
};

export default UserNode;
