import React, { useCallback } from "react";
import { NODE_BASE_STYLES, NODE_SELECTED_CLASS_COMPACT, type NodeProps } from "../utils/types";
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
            className={`${NODE_BASE_STYLES.CONDITION_PILL} border border-(--color-secondary-w20) bg-(--color-background-w10) text-(--color-secondary-text-wMain) ${isSelected ? NODE_SELECTED_CLASS_COMPACT : ""}`}
            style={{
                width: isDefault ? 'auto' : `${node.width}px`,
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
                <>
                    <span className="flex-shrink-0 font-medium">{caseNumber}</span>
                    <div className="h-4 w-px bg-(--color-secondary-w20) dark:bg-(--color-secondary-w80)" />
                </>
            )}
            <span className="block flex-1 overflow-hidden text-ellipsis whitespace-nowrap text-secondary-foreground">
                {displayText}
            </span>
        </div>
    );
};

export default ConditionPillNode;
