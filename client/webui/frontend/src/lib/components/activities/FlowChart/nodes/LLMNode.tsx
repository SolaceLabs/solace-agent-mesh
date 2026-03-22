import type { FC } from "react";
import { Sparkles } from "lucide-react";

import type { LayoutNode } from "../utils/types";
import { ACTIVITY_NODE_BASE_STYLES, ACTIVITY_NODE_SELECTED_CLASS, ACTIVITY_NODE_PROCESSING_CLASS } from "../utils/nodeStyles";
import { NODE_COLORS } from "@/lib/constants";
import { clickableNodeProps } from "@/lib/components/utils";

interface LLMNodeProps {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
}

const LLMNode: FC<LLMNodeProps> = ({ node, isSelected, onClick }) => {
    const isProcessing = node.data.status === "in-progress";
    const haloClass = isProcessing ? ACTIVITY_NODE_PROCESSING_CLASS : "";

    return (
        <div {...clickableNodeProps(() => onClick?.(node))} className={`${ACTIVITY_NODE_BASE_STYLES.RECTANGULAR_COMPACT} ${isSelected ? ACTIVITY_NODE_SELECTED_CLASS : ""} ${haloClass}`}>
            <div className="flex items-center gap-2">
                <Sparkles className={`h-4 w-4 flex-shrink-0 ${NODE_COLORS.llm}`} />
                <div className="truncate text-sm font-semibold">{node.data.label}</div>
            </div>
        </div>
    );
};

export default LLMNode;
