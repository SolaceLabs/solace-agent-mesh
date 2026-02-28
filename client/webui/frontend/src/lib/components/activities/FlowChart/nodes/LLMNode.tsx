import type { FC } from "react";
import { Sparkles } from "lucide-react";

import type { LayoutNode } from "../utils/types";
import { ACTIVITY_NODE_BASE_STYLES, ACTIVITY_NODE_SELECTED_CLASS, ACTIVITY_NODE_PROCESSING_CLASS } from "../utils/nodeStyles";

interface LLMNodeProps {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
}

const LLMNode: FC<LLMNodeProps> = ({ node, isSelected, onClick }) => {
    const isProcessing = node.data.status === "in-progress";
    const haloClass = isProcessing ? ACTIVITY_NODE_PROCESSING_CLASS : "";

    return (
        <div
            className={`${ACTIVITY_NODE_BASE_STYLES.RECTANGULAR_COMPACT} ${isSelected ? ACTIVITY_NODE_SELECTED_CLASS : ""} ${haloClass}`}
            onClick={e => {
                e.stopPropagation();
                onClick?.(node);
            }}
        >
            <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 flex-shrink-0 text-teal-600 dark:text-teal-400" />
                <div className="truncate text-sm font-semibold">{node.data.label}</div>
            </div>
        </div>
    );
};

export default LLMNode;
