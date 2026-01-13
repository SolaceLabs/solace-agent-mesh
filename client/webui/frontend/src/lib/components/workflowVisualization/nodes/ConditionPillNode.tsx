import React, { useCallback } from "react";
import { NODE_SELECTED_CLASSES, type NodeProps } from "../utils/types";
import { getValidNodeReferences } from "../utils/expressionParser";

/**
 * Condition pill node - Small pill showing a switch case condition with case number
 * Positioned above the target node with curved edge from switch and straight edge to target
 * Supports highlighting source nodes on hover by parsing expression references
 */
const ConditionPillNode: React.FC<NodeProps> = ({ node, isSelected, onClick, onHighlightNodes, knownNodeIds }) => {
    const isDefault = node.data.isDefaultCase;
    const label = node.data.conditionLabel || node.data.label;
    const caseNumber = node.data.caseNumber;

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

    // Format display text with case number prefix
    const displayText = isDefault ? "Default" : label;
    const fullText = isDefault ? "Default" : `${caseNumber} ${label}`;

    return (
        <div
            className={`flex cursor-pointer items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium shadow-sm transition-all duration-200 ${
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
            title={fullText}
        >
            {!isDefault && caseNumber && (
                <span className="flex-shrink-0 font-semibold">{caseNumber}</span>
            )}
            <span className="block flex-1 overflow-hidden text-ellipsis whitespace-nowrap">
                {displayText}
            </span>
        </div>
    );
};

export default ConditionPillNode;
