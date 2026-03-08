import type { FC } from "react";
import { Play } from "lucide-react";
import { NODE_BASE_STYLES, NODE_HIGHLIGHT_CLASSES, type NodeProps } from "../utils/types";

/**
 * Start node - Pill-shaped node marking the beginning of the workflow
 * Supports highlighting when referenced via workflow.input in expressions
 */
const StartNode: FC<NodeProps> = ({ node, isHighlighted }) => {
    return (
        <div
            className={`${NODE_BASE_STYLES.PILL} ${isHighlighted ? NODE_HIGHLIGHT_CLASSES : ""}`}
            style={{
                width: `${node.width}px`,
                height: `${node.height}px`,
            }}
        >
            <Play className="h-4 w-4" />
            <span className="text-sm font-semibold">{node.data.label}</span>
        </div>
    );
};

export default StartNode;
