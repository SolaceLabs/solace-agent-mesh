import type { FC } from "react";
import { GitBranch } from "lucide-react";

import type { LayoutNode } from "../utils/types";
import { ACTIVITY_NODE_BASE_STYLES, ACTIVITY_NODE_SELECTED_CLASS } from "../utils/nodeStyles";

interface SwitchNodeProps {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
}

const SwitchNode: FC<SwitchNodeProps> = ({ node, isSelected, onClick }) => {
    const casesCount = node.data.cases?.length || 0;
    const hasDefault = !!node.data.defaultBranch;
    const totalCases = casesCount + (hasDefault ? 1 : 0);
    const selectedBranch = node.data.selectedBranch;

    return (
        <div
            className={`${ACTIVITY_NODE_BASE_STYLES.CONTAINER_HEADER} ${isSelected ? ACTIVITY_NODE_SELECTED_CLASS : ""}`}
            style={{ width: 'fit-content', minWidth: '280px' }}
            onClick={e => {
                e.stopPropagation();
                onClick?.(node);
            }}
        >
            {/* Header row */}
            <div className="flex items-center gap-4 px-4 py-2">
                <div className="flex items-center gap-2">
                    <GitBranch className="h-4 w-4 text-(--color-accent-n0-wMain)" />
                    <span className="text-sm font-semibold">Switch</span>
                </div>
                {totalCases > 0 && <span className="text-sm text-gray-500 dark:text-gray-400">{totalCases} cases</span>}
            </div>

            {/* Selected case display - only show if a branch was selected */}
            {selectedBranch && (
                <div className="px-4 pt-0 pb-3">
                    <span className="text-secondary-foreground block truncate rounded bg-(--color-secondary-w10) px-2 py-1 text-sm dark:bg-(--color-secondary-w80)" title={selectedBranch}>
                        {selectedBranch === "default" ? "default" : selectedBranch}
                    </span>
                </div>
            )}
        </div>
    );
};

export default SwitchNode;
