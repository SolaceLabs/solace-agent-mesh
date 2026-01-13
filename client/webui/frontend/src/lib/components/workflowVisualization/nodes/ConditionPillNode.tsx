import React, { useCallback } from "react";
import { NODE_SELECTED_CLASSES, type NodeProps } from "../utils/types";
import { getValidNodeReferences } from "../utils/expressionParser";

/**
 * Condition pill node - Small pill showing a switch case condition
 * Positioned above the target node with curved edge from switch and straight edge to target
 * Supports highlighting source nodes on hover by parsing expression references
 */
const ConditionPillNode: React.FC<NodeProps> = ({ node, isSelected, onClick, onHighlightNodes, knownNodeIds }) => {
    const isDefault = node.data.isDefaultCase;
    const label = node.data.conditionLabel || node.data.label;

    // Handle mouse enter - extract node references and highlight them
    const handleMouseEnter = useCallback(() => {
        if (!onHighlightNodes || !knownNodeIds || !label) return;
        const nodeRefs = getValidNodeReferences(label, knownNodeIds);
        if (nodeRefs.length > 0) {
            onHighlightNodes(nodeRefs);
        }
    }, [label, onHighlightNodes, knownNodeIds]);

    // Handle mouse leave - clear highlights
    const handleMouseLeave = useCallback(() => {
        onHighlightNodes?.([]);
    }, [onHighlightNodes]);

    return (
        <div
            className={`flex cursor-pointer items-center justify-center rounded-full border px-2 py-1 text-xs font-medium shadow-sm transition-all duration-200 ${
                isDefault
                    ? "border-amber-400 bg-amber-50 text-amber-700 dark:border-amber-500 dark:bg-amber-900/30 dark:text-amber-300"
                    : "border-purple-400 bg-purple-50 text-purple-700 dark:border-purple-500 dark:bg-purple-900/30 dark:text-purple-300"
            } ${isSelected ? NODE_SELECTED_CLASSES.BLUE_COMPACT : ""}`}
            style={{
                width: `${node.width}px`,
                height: `${node.height}px`,
            }}
            onClick={e => {
                e.stopPropagation();
                onClick?.(node);
            }}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
            title={label}
        >
            <span className="block w-full overflow-hidden text-ellipsis whitespace-nowrap text-center">{label}</span>
        </div>
    );
};

export default ConditionPillNode;
