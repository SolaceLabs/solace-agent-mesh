import type { FC } from "react";
import { Play } from "lucide-react";
import { NODE_HIGHLIGHT_CLASSES, NODE_SELECTED_CLASSES, type NodeProps } from "../utils/types";

/**
 * Start node - Pill-shaped node marking the beginning of the workflow
 * Supports highlighting when referenced via workflow.input in expressions
 */
const StartNode: FC<NodeProps> = ({ node, isSelected, isHighlighted, onClick }) => {
    return (
        <div
            className={`flex cursor-pointer items-center justify-center gap-2 rounded-full border-2 border-(--color-accent-n1-wMain) bg-(--color-accent-n1-w10) px-4 py-2 shadow-sm transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-md dark:border-(--color-accent-n1-w60) dark:bg-(--color-accent-n1-w100)/50 ${
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
            <Play className="h-4 w-4 text-(--color-accent-n1-wMain) dark:text-(--color-accent-n1-w30)" />
            <span className="text-sm font-semibold text-(--color-accent-n1-w100) dark:text-(--color-accent-n1-w10)">{node.data.label}</span>
        </div>
    );
};

export default StartNode;
