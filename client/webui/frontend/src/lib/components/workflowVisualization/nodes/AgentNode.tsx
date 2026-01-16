import type { FC } from "react";
import { Bot } from "lucide-react";
import { NODE_HIGHLIGHT_CLASSES, NODE_SELECTED_CLASSES, type NodeProps } from "../utils/types";

/**
 * Agent node - Rectangle with robot icon, agent name, and "Agent" badge
 * Supports highlighting when referenced in expressions (shown with amber glow)
 */
const AgentNode: FC<NodeProps> = ({ node, isSelected, isHighlighted, onClick }) => {
    const agentName = node.data.agentName || node.data.label;

    return (
        <div
            className={`group relative flex cursor-pointer items-center justify-between rounded-lg border-2 border-(--color-info-wMain) bg-(--color-background-w10) px-4 py-3 shadow-sm transition-all duration-200 ease-in-out hover:shadow-md dark:border-(--color-info-w70) dark:bg-(--color-background-wMain) ${
                isSelected ? NODE_SELECTED_CLASSES.BLUE : ""
            } ${isHighlighted ? NODE_HIGHLIGHT_CLASSES : ""}`}
            style={{
                width: `${node.width}px`,
                height: `${node.height}px`,
            }}
            onClick={e => {
                e.stopPropagation();
                onClick?.(node);
            }}
        >
            <div className="flex items-center gap-2 overflow-hidden">
                <Bot className="h-5 w-5 flex-shrink-0 text-(--color-info-wMain) dark:text-(--color-info-w70)" />
                <span className="truncate text-sm font-medium text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10)">{agentName}</span>
            </div>
            <span className="ml-2 flex-shrink-0 rounded bg-(--color-info-w10) px-2 py-0.5 text-xs font-medium text-(--color-info-w100) dark:bg-(--color-info-w100)/50 dark:text-(--color-info-w30)">
                Agent
            </span>
        </div>
    );
};

export default AgentNode;
