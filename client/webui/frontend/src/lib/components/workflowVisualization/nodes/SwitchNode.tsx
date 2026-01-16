import type { FC } from "react";
import { GitBranch } from "lucide-react";
import { NODE_HIGHLIGHT_CLASSES, NODE_SELECTED_CLASSES, type NodeProps } from "../utils/types";

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
            className={`group relative cursor-pointer rounded-lg border-2 border-(--color-accent-n3-wMain) bg-(--color-background-w10) shadow-sm transition-all duration-200 hover:shadow-md dark:border-(--color-accent-n3-w30) dark:bg-(--color-background-wMain) ${
                isSelected ? NODE_SELECTED_CLASSES.PURPLE : ""
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
            <div className="flex items-center justify-between px-3 py-2">
                <div className="flex items-center gap-2">
                    <GitBranch className="h-4 w-4 text-(--color-accent-n3-wMain) dark:text-(--color-accent-n3-w30)" />
                    <span className="text-sm font-medium text-(--color-accent-n3-w100) dark:text-(--color-accent-n3-w10)">Switch</span>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-xs text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50)">{totalCases} cases</span>
                    <span className="rounded bg-(--color-accent-n3-w10) px-1.5 py-0.5 text-xs font-medium text-(--color-accent-n3-w100) dark:bg-(--color-accent-n3-w100)/50 dark:text-(--color-accent-n3-w30)">
                        Switch
                    </span>
                </div>
            </div>

            {/* Case rows */}
            {totalCases > 0 && (
                <div className="border-t border-(--color-accent-n3-w30) px-3 py-2 dark:border-(--color-accent-n3-w100)/50">
                    <div className="flex flex-col gap-1.5">
                        {cases.map((caseItem: { condition?: string }, index: number) => (
                            <div key={index} className="flex items-center gap-2">
                                <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded bg-(--color-accent-n3-w10) text-xs font-medium text-(--color-accent-n3-w100) dark:bg-(--color-accent-n3-w100)/50 dark:text-(--color-accent-n3-w30)">
                                    {index + 1}
                                </span>
                                <span
                                    className="flex-1 truncate rounded bg-(--color-secondary-w10) px-2 py-0.5 text-xs text-(--color-secondary-text-wMain) dark:bg-(--color-secondary-w70) dark:text-(--color-secondary-text-w50)"
                                    title={caseItem.condition}
                                >
                                    {caseItem.condition || ""}
                                </span>
                            </div>
                        ))}
                        {hasDefault && (
                            <div className="flex items-center gap-2">
                                <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded bg-(--color-warning-w10) text-xs font-medium text-(--color-warning-w100) dark:bg-(--color-warning-w100)/50 dark:text-(--color-warning-w30)">
                                    {cases.length + 1}
                                </span>
                                <span className="flex-1 rounded bg-(--color-secondary-w10) px-2 py-0.5 text-xs text-(--color-secondary-text-wMain) dark:bg-(--color-secondary-w70) dark:text-(--color-secondary-text-w50)">
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
