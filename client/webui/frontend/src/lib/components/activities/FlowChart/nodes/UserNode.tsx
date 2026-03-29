import type { FC } from "react";
import { User } from "lucide-react";

import type { LayoutNode } from "../utils/types";
import { ACTIVITY_NODE_BASE_STYLES, ACTIVITY_NODE_SELECTED_CLASS } from "../utils/nodeStyles";
import { clickableNodeProps } from "@/lib/components/utils";

interface UserNodeProps {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
}

const UserNode: FC<UserNodeProps> = ({ node, isSelected, onClick }) => {
    const USER_WIDTH = 100;

    return (
        <div {...clickableNodeProps(() => onClick?.(node))} className={`${ACTIVITY_NODE_BASE_STYLES.RECTANGULAR} ${isSelected ? ACTIVITY_NODE_SELECTED_CLASS : ""}`} style={{ width: `${USER_WIDTH}px` }}>
            <div className="flex items-center gap-2" data-testid="userNode">
                <User className="h-4 w-4 flex-shrink-0 text-(--brand-wMain)" />
                <div className="text-sm font-semibold">{node.data.label}</div>
            </div>
        </div>
    );
};

export default UserNode;
