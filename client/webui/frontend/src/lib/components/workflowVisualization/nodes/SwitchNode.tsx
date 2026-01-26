import type { FC } from "react";
import { GitBranch } from "lucide-react";
import { NODE_BASE_STYLES, NODE_HIGHLIGHT_CLASSES, NODE_SELECTED_CLASS, type NodeProps } from "../utils/types";

/**
 * Switch node - Shows conditional branching with case rows inside
 * When there are few cases, shows numbered rows with condition previews
 * Supports highlighting when referenced in expressions
 */
const SwitchNode: FC<NodeProps> = ({ node, isSelected, isHighlighted, onClick }) => {
    const cases = node.data.cases || [];
    const hasDefault = !!node.data.defaultCase;
    const totalCases = cases.length + (hasDefault ? 1 : 0);

    return (
        <div
            className={`${NODE_BASE_STYLES.SWITCH} ${
                isSelected ? NODE_SELECTED_CLASS : ""
            } ${isHighlighted ? NODE_HIGHLIGHT_CLASSES : ""}`}
            style={{
                width: `${node.width}px`,
            }}
            onClick={e => {
                e.stopPropagation();
                onClick?.(node);
            }}
        >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3">
                <div className="flex items-center gap-2">
                    <GitBranch className="h-4 w-4 text-(--color-accent-n0-wMain)" />
                    <span className="text-sm font-semibold">Switch</span>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-500 dark:text-gray-400">{totalCases} cases</span>
                </div>
            </div>

            {/* Case rows */}
            {totalCases > 0 && (
                <div className="px-4 pb-3 pt-0">
                    <div className="flex flex-col gap-1.5">
                        {cases.map((caseItem: { condition?: string }, index: number) => (
                            <div key={index} className="flex items-center gap-2 ">
                                <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded border border-(--color-secondary-w20) text-xs font-medium text-secondary-foreground dark:border dark:border-(--color-secondary-w80)">
                                    {index + 1}
                                </span>
                                <span
                                className="block truncate rounded bg-(--color-secondary-w10) dark:bg-(--color-secondary-w80) px-2 py-1 text-sm text-secondary-foreground dark:border dark:border-(--color-secondary-w80)"
                                    title={caseItem.condition}
                                >
                                    {caseItem.condition || ""}
                                </span>
                            </div>
                        ))}
                        {hasDefault && (
                            <div className="flex items-center gap-2">
                                <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded border border-(--color-secondary-w20) text-xs font-medium dark:border-(--color-secondary-w80)">
                                    {cases.length + 1}
                                </span>
                                <span className="flex-1 rounded bg-(--color-secondary-w10) dark:bg-(--color-secondary-w80) px-2 py-1 text-sm text-secondary-foreground dark:border dark:border-(--color-secondary-w80)">
                                    default
                                </span>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default SwitchNode;
