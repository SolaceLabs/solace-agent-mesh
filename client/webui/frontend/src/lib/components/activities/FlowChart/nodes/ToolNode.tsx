import type { FC } from "react";
import { Wrench } from "lucide-react";

import type { LayoutNode } from "../utils/types";
import { ACTIVITY_NODE_BASE_STYLES, ACTIVITY_NODE_SELECTED_CLASS, ACTIVITY_NODE_PROCESSING_CLASS } from "../utils/nodeStyles";

interface ToolNodeProps {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
}

const ToolNode: FC<ToolNodeProps> = ({ node, isSelected, onClick }) => {
    const isProcessing = node.data.status === "in-progress";
    const haloClass = isProcessing ? ACTIVITY_NODE_PROCESSING_CLASS : "";
    const artifactCount = node.data.createdArtifacts?.length || 0;

    return (
        <div
            className={`${ACTIVITY_NODE_BASE_STYLES.CONTAINER_HEADER} ${isSelected ? ACTIVITY_NODE_SELECTED_CLASS : ""} ${haloClass}`}
            style={{ width: '225px' }}
            onClick={e => {
                e.stopPropagation();
                onClick?.(node);
            }}
        >
            <div className="flex items-center gap-2 px-4 py-2">
                <Wrench className="h-4 w-4 flex-shrink-0 text-cyan-600 dark:text-cyan-400" />
                <div className="truncate text-sm font-semibold">{node.data.label}</div>
            </div>
            {artifactCount > 0 && (
                <div className="px-4 pt-0 pb-2 pl-10">
                    <div className="text-xs text-(--color-secondary-text-wMain)">
                        {artifactCount} {artifactCount === 1 ? "artifact" : "artifacts"} created
                    </div>
                </div>
            )}
        </div>
    );
};

export default ToolNode;
