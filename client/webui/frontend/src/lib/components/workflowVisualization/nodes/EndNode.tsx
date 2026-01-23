import type { FC } from "react";
import { CheckCircle } from "lucide-react";
import { NODE_BASE_STYLES, NODE_SELECTED_CLASS, type NodeProps } from "../utils/types";

/**
 * End node - Pill-shaped node marking the end of the workflow
 */
const EndNode: FC<NodeProps> = ({ node, isSelected, onClick }) => {
    return (
        <div
            className={`${NODE_BASE_STYLES.PILL} ${
                isSelected ? NODE_SELECTED_CLASS : ""
            }`}
            style={{
                width: `${node.width}px`,
                height: `${node.height}px`,
            }}
            onClick={e => {
                e.stopPropagation();
                onClick?.(node);
            }}
        >
            <CheckCircle className="h-4 w-4" />
            <span className="text-sm font-semibold">{node.data.label}</span>
        </div>
    );
};

export default EndNode;
