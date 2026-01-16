import React from "react";
import { CheckCircle } from "lucide-react";
import { NODE_BASE_STYLES, NODE_SELECTED_CLASS, type NodeProps } from "../utils/types";

/**
 * End node - Pill-shaped node marking the end of the workflow
 */
const EndNode: React.FC<NodeProps> = ({ node, isSelected, onClick }) => {
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
            <CheckCircle className="h-4 w-4 text-indigo-600 dark:text-indigo-300" />
            <span className="text-sm font-semibold text-indigo-900 dark:text-indigo-100">{node.data.label}</span>
        </div>
    );
};

export default EndNode;
